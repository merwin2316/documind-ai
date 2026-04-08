"""
Document service for managing documents.
"""
import uuid
from datetime import datetime
from typing import List, Optional, Dict
from fastapi import UploadFile
from app.database.supabase_client import get_supabase_client
from app.models.document import Document
from app.services.document_processor import DocumentProcessor
from app.services.vector_store import VectorStore
from app.services.websocket_manager import get_connection_manager
from config import settings


class DocumentService:
    """Service for document management operations."""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
    
    async def upload_and_process(
        self, 
        file: UploadFile, 
        filename: str, 
        file_size: int
    ) -> Dict:
        """
        Upload document to Supabase Storage and initiate processing.
        """
        # Generate unique document ID
        document_id = str(uuid.uuid4())
        
        # Sanitize filename for Supabase Storage
        # Remove special characters, replace spaces with underscores
        import re
        safe_filename = re.sub(r'[^\w\s.-]', '', filename)  # Remove special chars
        safe_filename = re.sub(r'\s+', '_', safe_filename)  # Replace spaces with underscores
        safe_filename = safe_filename.strip('._')  # Remove leading/trailing dots/underscores
        
        # Create storage path with sanitized filename
        storage_path = f"{self.user_id}/{document_id}/{safe_filename}"
        
        # Get Supabase client
        supabase = await get_supabase_client()
        
        # Determine file type
        if filename.lower().endswith('.pdf'):
            content_type = "application/pdf"
        elif filename.lower().endswith('.docx'):
            content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        else:
            raise ValueError(f"Unsupported file type: {filename}")
        
        # Upload to Supabase Storage
        file_content = await file.read()
        supabase.storage.from_(settings.STORAGE_BUCKET).upload(
            storage_path,
            file_content,
            file_options={"content-type": content_type, "upsert": "false"}
        )
        
        # Create document record in database
        document_data = {
            "document_id": document_id,
            "user_id": self.user_id,
            "name": filename,
            "storage_path": storage_path,
            "file_size": file_size,
            "file_type": content_type,
            "status": "processing"
        }
        
        supabase.table("documents").insert(document_data).execute()
        
        # Process document asynchronously (in production, use background task queue like Celery)
        # For now, process synchronously - in production, enqueue this as a background task
        await self._process_document(document_id, file_content, filename)
        
        # Get updated status after processing
        updated_doc = supabase.table("documents").select("status").eq("document_id", document_id).execute()
        final_status = updated_doc.data[0]["status"] if updated_doc.data else "processing"
        
        return {
            "document_id": document_id,
            "name": filename,
            "status": final_status
        }
    
    async def _process_document(self, document_id: str, file_content: bytes, filename: str):
        """
        Process document: extract text, chunk, create embeddings, store in Qdrant.
        NOW WITH AI CATEGORIZATION: Auto-categorize, tag, and summarize documents.
        Supports both PDF and DOCX files.
        """
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            logger.info(f"Starting processing for document {document_id}")
            
            # Process document (PDF or DOCX)
            document_processor = DocumentProcessor()
            chunks = await document_processor.process_document(file_content, filename, document_id, self.user_id)
            
            # Validate chunks were created
            if not chunks:
                raise ValueError("No text could be extracted from the document. The file may be empty or corrupted.")
            
            logger.info(f"Created {len(chunks)} chunks for document {document_id}")
            
            # Store in vector database
            vector_store = VectorStore()
            await vector_store.store_chunks(chunks, document_id, self.user_id)
            
            logger.info(f"Stored chunks in vector database for document {document_id}")
            
            # ========== NEW: AI CATEGORIZATION ==========
            try:
                from app.agents.categorization_agent import CategorizationAgent
                
                categorization_agent = CategorizationAgent()
                
                # Get sample text from first few chunks
                sample_text = " ".join([chunk["text"] for chunk in chunks[:5]])
                
                # Categorize document
                logger.info(f"Starting AI categorization for document {document_id}")
                metadata = await categorization_agent.categorize_document(sample_text, filename)
                logger.info(f"AI categorization complete: category={metadata['category']}, tags={metadata['tags']}")
                
                # Find related documents (async, non-blocking)
                logger.info(f"Finding related documents for {document_id}")
                related_ids = await categorization_agent.find_related_documents(
                    document_id, self.user_id, top_k=5
                )
                logger.info(f"Found {len(related_ids)} related documents")
                
            except Exception as cat_error:
                # Don't fail entire processing if categorization fails
                logger.warning(f"AI categorization failed for {document_id}: {cat_error}")
                metadata = {
                    "category": "Other",
                    "tags": [],
                    "summary": f"Document: {filename}",
                    "key_entities": {"people": [], "companies": [], "products": []}
                }
                related_ids = []
            # ============================================
            
            # Calculate document statistics
            max_page = max(chunk["page"] for chunk in chunks) if chunks else 0
            unique_pages = len(set(chunk["page"] for chunk in chunks)) if chunks else 0
            
            # Update document status WITH AI METADATA
            supabase = await get_supabase_client()
            supabase.table("documents").update({
                "status": "ready",
                "total_pages": max_page,
                "total_chunks": len(chunks),
                "processed_at": datetime.utcnow().isoformat(),
                # AI-generated metadata
                "category": metadata["category"],
                "tags": metadata["tags"],
                "ai_summary": metadata["summary"],
                "key_entities": metadata["key_entities"],
                "related_document_ids": related_ids
            }).eq("document_id", document_id).execute()
            
            logger.info(f"Document {document_id} processed successfully: {len(chunks)} chunks across {unique_pages} unique pages (max page: {max_page})")
            logger.info(f"AI metadata: category={metadata['category']}, tags={len(metadata['tags'])}, related_docs={len(related_ids)}")
            
            # Broadcast ready status with AI metadata
            await get_connection_manager().broadcast_to_user(self.user_id, {
                "document_id": document_id,
                "status": "ready",
                "total_pages": max_page,
                "total_chunks": len(chunks),
                "category": metadata["category"],
                "tags": metadata["tags"]
            })
            
        except ValueError as e:
            # User-friendly errors (empty document, unsupported format, etc.)
            error_message = str(e)
            logger.error(f"Document processing failed for {document_id}: {error_message}")
            supabase = await get_supabase_client()
            supabase.table("documents").update({
                "status": "error",
                "error_message": error_message
            }).eq("document_id", document_id).execute()
            
            # Broadcast error status
            await get_connection_manager().broadcast_to_user(self.user_id, {
                "document_id": document_id,
                "status": "error",
                "error_message": error_message
            })
            
        except Exception as e:
            # Generic errors (network issues, API failures, etc.)
            error_type = type(e).__name__
            error_message = f"Processing failed: {str(e)}"
            logger.error(f"Unexpected error processing document {document_id}: {error_type}: {str(e)}", exc_info=True)
            supabase = await get_supabase_client()
            supabase.table("documents").update({
                "status": "error",
                "error_message": error_message
            }).eq("document_id", document_id).execute()
            
            # Broadcast error status
            await get_connection_manager().broadcast_to_user(self.user_id, {
                "document_id": document_id,
                "status": "error",
                "error_message": error_message
            })
            raise
    
    async def list_documents(self, skip: int = 0, limit: int = 20) -> tuple[List[Document], int]:
        """List all documents for the user."""
        import asyncio
        supabase = await get_supabase_client()
        loop = asyncio.get_event_loop()
        
        # Run synchronous DB queries in thread pool
        
        # Get total count
        count_result = await loop.run_in_executor(
            None,
            lambda: supabase.table("documents").select("*", count="exact").eq("user_id", self.user_id).execute()
        )
        total = count_result.count if hasattr(count_result, 'count') else 0
        
        # Get documents
        result = await loop.run_in_executor(
            None,
            lambda: supabase.table("documents").select("*").eq("user_id", self.user_id).order("uploaded_at", desc=True).range(skip, skip + limit - 1).execute()
        )
        
        documents = [Document(**doc) for doc in result.data]
        return documents, total
    
    async def get_document(self, document_id: str) -> Optional[Document]:
        """Get a specific document."""
        import asyncio
        supabase = await get_supabase_client()
        
        # Run synchronous DB query in thread pool to avoid blocking event loop
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                None,
                lambda: supabase.table("documents").select("*").eq("document_id", document_id).eq("user_id", self.user_id).execute()
            )
            
            if result.data:
                return Document(**result.data[0])
            return None
        except Exception as e:
            # Handle potential errors during execution
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error getting document {document_id}: {e}")
            raise
    
    async def delete_document(self, document_id: str) -> bool:
        """Delete a document and all associated data."""
        import logging
        logger = logging.getLogger(__name__)
        
        supabase = await get_supabase_client()
        
        # Get document to verify ownership
        document = await self.get_document(document_id)
        if not document:
            return False
        
        logger.info(f"Deleting document {document_id} and all associated data")
        
        # 1. Delete chunks from Supabase database
        try:
            chunks_result = supabase.table("document_chunks").delete().eq("document_id", document_id).execute()
            logger.info(f"Deleted {len(chunks_result.data) if chunks_result.data else 0} chunks from Supabase for document {document_id}")
        except Exception as e:
            logger.error(f"Error deleting chunks from Supabase: {e}")
        
        # 2. Delete from vector store (Qdrant)
        try:
            vector_store = VectorStore()
            await vector_store.delete_document_chunks(document_id, self.user_id)
            logger.info(f"Deleted chunks from Qdrant for document {document_id}")
        except Exception as e:
            logger.error(f"Error deleting from Qdrant: {e}")
        
        # 3. Delete from storage (Supabase Storage)
        try:
            supabase.storage.from_(settings.STORAGE_BUCKET).remove([document.storage_path])
            logger.info(f"Deleted file from storage: {document.storage_path}")
        except Exception as e:
            logger.warning(f"Error deleting from storage: {e}")
        
        # 4. Delete citations (if any)
        try:
            citations_result = supabase.table("citations").delete().eq("document_id", document_id).execute()
            logger.info(f"Deleted {len(citations_result.data) if citations_result.data else 0} citations for document {document_id}")
        except Exception as e:
            logger.error(f"Error deleting citations: {e}")
        
        # 5. Delete document record from database
        try:
            supabase.table("documents").delete().eq("document_id", document_id).eq("user_id", self.user_id).execute()
            logger.info(f"Deleted document record {document_id}")
        except Exception as e:
            logger.error(f"Error deleting document record: {e}")
            return False
        
        logger.info(f"Successfully deleted document {document_id} and all associated data")
        return True
    
    async def get_signed_url(self, document_id: str, expires_in: int = 3600) -> str:
        """Get a signed URL for document download."""
        import logging
        import asyncio
        
        logger = logging.getLogger(__name__)
        
        document = await self.get_document(document_id)
        if not document:
            raise ValueError("Document not found")
        
        supabase = await get_supabase_client()
        
        try:
            # Wrap synchronous Supabase call in async timeout (10 seconds)
            # Supabase storage operations are synchronous, so we run them with a timeout
            logger.info(f"Creating signed URL for document {document_id} at path: {document.storage_path}")
            
            # Run the synchronous operation in a thread pool with timeout
            loop = asyncio.get_event_loop()
            url_response = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: supabase.storage.from_(settings.STORAGE_BUCKET).create_signed_url(
                        document.storage_path,
                        expires_in
                    )
                ),
                timeout=10.0  # 10 second timeout
            )
            
            logger.info(f"Successfully created signed URL for document {document_id}")
            return url_response["signedURL"]
            
        except asyncio.TimeoutError:
            logger.error(f"Timeout creating signed URL for document {document_id}")
            raise ValueError("Timeout creating signed URL. Please try again.")
        except Exception as e:
            logger.error(f"Error creating signed URL for document {document_id}: {str(e)}")
            raise ValueError(f"Error creating signed URL: {str(e)}")

