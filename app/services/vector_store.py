"""
Vector store service using Qdrant.
Embeddings via the configured LLM provider (Ollama by default).
"""
from typing import List, Dict, Optional
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, Filter,
    FieldCondition, MatchValue, MatchAny, FilterSelector,
    PayloadSchemaType,
)
from shared.llm.factory import get_llm_provider
from config import settings
import logging

logger = logging.getLogger(__name__)


class VectorStore:
    """Service for managing vector embeddings in Qdrant (Async)."""

    def __init__(self):
        client_kwargs = {"url": settings.QDRANT_URL}
        if settings.QDRANT_API_KEY:
            client_kwargs["api_key"] = settings.QDRANT_API_KEY
        self.client = AsyncQdrantClient(**client_kwargs)

        self.llm = get_llm_provider()
        self.collection_name = "document_chunks"

    async def _ensure_collection(self):
        """Create collection if it doesn't exist, and ensure indexes."""
        from qdrant_client.http.exceptions import UnexpectedResponse

        dims = self.llm.embedding_dimensions

        try:
            await self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=dims,
                    distance=Distance.COSINE,
                ),
            )
            logger.info(
                f"Created Qdrant collection '{self.collection_name}' "
                f"(dims={dims})"
            )
        except UnexpectedResponse as e:
            msg = str(e).lower()
            if "409" in str(e) or "already exists" in msg or "conflict" in msg:
                pass
            else:
                logger.warning(f"Unexpected error creating collection: {e}")
        except Exception as e:
            logger.warning(f"Error creating collection: {type(e).__name__}: {e}")

        # Ensure payload indexes for filtering
        for field in ("user_id", "document_id"):
            try:
                await self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field,
                    field_schema=PayloadSchemaType.KEYWORD,
                )
            except Exception:
                pass

    async def store_chunks(
        self, chunks: List[Dict], document_id: str, user_id: str
    ):
        """Embed chunks and store in Qdrant."""
        if not chunks:
            return

        await self._ensure_collection()

        texts = [c["text"] for c in chunks]
        embeddings = await self.llm.create_embeddings(texts)

        points = [
            PointStruct(
                id=chunk["chunk_id"],
                vector=emb,
                payload={
                    "document_id": document_id,
                    "user_id": user_id,
                    "page": chunk["page"],
                    "start_char": chunk["start_char"],
                    "end_char": chunk["end_char"],
                    "text": chunk["text"],
                },
            )
            for chunk, emb in zip(chunks, embeddings)
        ]

        await self.client.upsert(
            collection_name=self.collection_name, points=points
        )

    async def search(
        self,
        query: str,
        user_id: str,
        top_k: int = None,
        document_ids: Optional[List[str]] = None,
        chunk_id: Optional[str] = None,
    ) -> List[Dict]:
        """Search for relevant chunks using vector similarity."""
        if top_k is None:
            top_k = settings.TOP_K_RETRIEVAL

        await self._ensure_collection()

        query_embedding = None

        # If chunk_id provided, use its vector as query
        if chunk_id:
            try:
                points = await self.client.retrieve(
                    collection_name=self.collection_name,
                    ids=[chunk_id],
                    with_vectors=True,
                )
                if points and points[0].vector:
                    query_embedding = points[0].vector
            except Exception as e:
                logger.warning(f"Failed to fetch vector for chunk {chunk_id}: {e}")

        if query_embedding is None:
            if not query:
                return []
            embeddings = await self.llm.create_embeddings([query])
            query_embedding = embeddings[0]

        # Build filter
        conditions = [
            FieldCondition(key="user_id", match=MatchValue(value=user_id))
        ]
        if document_ids:
            conditions.append(
                FieldCondition(key="document_id", match=MatchAny(any=document_ids))
            )
        query_filter = Filter(must=conditions)

        results = await self.client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            query_filter=query_filter,
            limit=top_k,
        )

        return [
            {
                "chunk_id": r.id,
                "score": r.score,
                "document_id": r.payload["document_id"],
                "page": r.payload["page"],
                "start_char": r.payload["start_char"],
                "end_char": r.payload["end_char"],
                "text": r.payload["text"],
            }
            for r in results
        ]

    async def delete_document_chunks(self, document_id: str, user_id: str):
        """Delete all chunks for a document from Qdrant."""
        await self._ensure_collection()

        query_filter = Filter(
            must=[
                FieldCondition(key="document_id", match=MatchValue(value=document_id)),
                FieldCondition(key="user_id", match=MatchValue(value=user_id)),
            ]
        )

        await self.client.delete(
            collection_name=self.collection_name,
            points_selector=FilterSelector(filter=query_filter),
        )
