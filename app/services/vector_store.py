"""
Vector store service using Qdrant.
"""
from typing import List, Dict, Optional
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue, MatchAny, FilterSelector, PayloadSchemaType
from openai import AsyncOpenAI
from config import settings


class VectorStore:
    """Service for managing vector embeddings in Qdrant (Async)."""
    
    def __init__(self):
        # Initialize Async Qdrant client
        client_kwargs = {"url": settings.QDRANT_URL}
        if settings.QDRANT_API_KEY:
            client_kwargs["api_key"] = settings.QDRANT_API_KEY
        
        self.client = AsyncQdrantClient(**client_kwargs)
        # Set timeout for OpenAI embedding API calls (60 seconds)
        self.openai_client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=60.0
        )
        self.collection_name = "document_chunks"
        # Note: _ensure_collection cannot be called in __init__ as it is async
        # It will be called lazily in methods that need it
    
    async def _ensure_collection(self):
        """Create collection if it doesn't exist, and ensure indexes are created."""
        from qdrant_client.http.exceptions import UnexpectedResponse
        
        # Try to create collection (will fail with 409 if it already exists)
        try:
            await self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=3072,  # text-embedding-3-large dimension
                    distance=Distance.COSINE
                )
            )
        except UnexpectedResponse as e:
            # 409 Conflict means collection already exists - that's fine, continue
            error_msg = str(e).lower()
            if "409" in str(e) or "already exists" in error_msg or "conflict" in error_msg:
                pass  # Collection exists, that's fine
            else:
                # Other unexpected errors - log but don't fail (might be version incompatibility)
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Unexpected error checking/creating collection: {e}")
        except Exception as e:
            # Any other exception (including ResponseHandlingException from version incompatibility)
            # Collection might exist - try to continue, operations will fail if it doesn't
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Error checking/creating collection: {type(e).__name__}: {e}")
        
        # Ensure indexes exist for filtering fields (required for Qdrant Cloud strict mode)
        try:
            # Create index for user_id (keyword type works for UUID strings)
            await self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="user_id",
                field_schema=PayloadSchemaType.KEYWORD
            )
        except Exception as e:
            # Index might already exist, ignore the error
            pass
        
        try:
            # Create index for document_id (keyword type works for UUID strings)
            await self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="document_id",
                field_schema=PayloadSchemaType.KEYWORD
            )
        except Exception as e:
            # Index might already exist, ignore the error
            pass
    
    async def store_chunks(
        self,
        chunks: List[Dict],
        document_id: str,
        user_id: str
    ):
        """
        Create embeddings for chunks and store in Qdrant.
        
        Each point in Qdrant contains:
        - id: chunk_id
        - vector: embedding
        - payload: {
            "document_id": str,
            "user_id": str,
            "page": int,
            "start_char": int,
            "end_char": int,
            "text": str
          }
        """
        if not chunks:
            return
            
        # Ensure collection exists before storing
        await self._ensure_collection()
        
        # Create embeddings for all chunks
        texts = [chunk["text"] for chunk in chunks]
        embeddings = await self._create_embeddings(texts)
        
        # Prepare points for Qdrant
        points = []
        for chunk, embedding in zip(chunks, embeddings):
            point = PointStruct(
                id=chunk["chunk_id"],
                vector=embedding,
                payload={
                    "document_id": document_id,
                    "user_id": user_id,
                    "page": chunk["page"],
                    "start_char": chunk["start_char"],
                    "end_char": chunk["end_char"],
                    "text": chunk["text"]
                }
            )
            points.append(point)
        
        # Upsert points to Qdrant
        await self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )
    
    async def _create_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Create embeddings using OpenAI."""
        response = await self.openai_client.embeddings.create(
            model=settings.OPENAI_EMBEDDING_MODEL,
            input=texts
        )
        return [item.embedding for item in response.data]
    
    async def search(
        self,
        query: str,
        user_id: str,
        top_k: int = None,
        document_ids: Optional[List[str]] = None,
        chunk_id: Optional[str] = None
    ) -> List[Dict]:
        """
        Search for relevant chunks using vector similarity.
        
        Args:
            query: User's question (ignored if chunk_id is provided)
            user_id: Filter by user_id
            top_k: Number of results to return
            document_ids: Optional filter by specific documents
            chunk_id: Optional chunk ID to use as query vector (for finding related docs)
        
        Returns:
            List of chunks with metadata and scores
        """
        if top_k is None:
            top_k = settings.TOP_K_RETRIEVAL
            
        # Ensure collection exists before searching
        await self._ensure_collection()
        
        query_embedding = None
        
        # If chunk_id is provided, fetch its vector to use as query
        if chunk_id:
            try:
                # Fetch point with vector
                points = await self.client.retrieve(
                    collection_name=self.collection_name,
                    ids=[chunk_id],
                    with_vectors=True
                )
                if points and points[0].vector:
                    query_embedding = points[0].vector
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to fetch vector for chunk_id {chunk_id}: {e}")
                
        # If no chunk vector found (or not provided), use text query
        if query_embedding is None:
            if not query:
                return []
            query_embeddings = await self._create_embeddings([query])
            query_embedding = query_embeddings[0]
        
        # Build filter using Qdrant Filter model
        from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchAny
        
        filter_conditions = []
        
        # Always filter by user_id
        filter_conditions.append(
            FieldCondition(
                key="user_id",
                match=MatchValue(value=user_id)
            )
        )
        
        if document_ids:
            filter_conditions.append(
                FieldCondition(
                    key="document_id",
                    match=MatchAny(any=document_ids)
                )
            )
        
        query_filter = Filter(must=filter_conditions) if filter_conditions else None
        
        # Search in Qdrant
        search_result = await self.client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            query_filter=query_filter,
            limit=top_k
        )
        
        # Format results
        results = []
        for result in search_result:
            results.append({
                "chunk_id": result.id,
                "score": result.score,
                "document_id": result.payload["document_id"],
                "page": result.payload["page"],
                "start_char": result.payload["start_char"],
                "end_char": result.payload["end_char"],
                "text": result.payload["text"]
            })
        
        return results
    
    async def delete_document_chunks(self, document_id: str, user_id: str):
        """Delete all chunks for a document from Qdrant."""
        from qdrant_client.models import Filter, FieldCondition, MatchValue, FilterSelector
        
        # Ensure collection exists
        await self._ensure_collection()
        
        # Delete by filter (document_id + user_id)
        filter_conditions = [
            FieldCondition(
                key="document_id",
                match=MatchValue(value=document_id)
            ),
            FieldCondition(
                key="user_id",
                match=MatchValue(value=user_id)
            )
        ]
        
        query_filter = Filter(must=filter_conditions)
        
        await self.client.delete(
            collection_name=self.collection_name,
            points_selector=FilterSelector(filter=query_filter)
        )
