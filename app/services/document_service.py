"""
Document service for managing documents.
Local SQLite + filesystem mode only.
"""
import os
import uuid
import logging
from datetime import datetime
from typing import List, Optional, Dict
from fastapi import UploadFile
from app.models.document import Document
from app.services.document_processor import DocumentProcessor
from app.services.vector_store import VectorStore
from app.services.websocket_manager import get_connection_manager
from config import settings

logger = logging.getLogger(__name__)


class DocumentService:
    """Service for document management operations."""

    def __init__(self, user_id: str):
        self.user_id = user_id

    # ================================================================
    # Upload & Process
    # ================================================================
    async def upload_and_process(self, file: UploadFile, filename: str, file_size: int) -> Dict:
        """Upload document and initiate processing."""
        import re

        document_id = str(uuid.uuid4())
        safe_filename = re.sub(r"[^\w\s.-]", "", filename)
        safe_filename = re.sub(r"\s+", "_", safe_filename).strip("._")
        storage_path = f"{self.user_id}/{document_id}/{safe_filename}"

        content_type = "application/pdf"
        if filename.lower().endswith(".docx"):
            content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        elif not filename.lower().endswith(".pdf"):
            raise ValueError(f"Unsupported file type: {filename}")

        file_content = await file.read()

        await self._upload_local(document_id, storage_path, file_content, filename, file_size, content_type)

        # Process document (extract text, chunk, embed)
        await self._process_document(document_id, file_content, filename)

        # Get final status
        final_status = await self._get_status(document_id)
        return {"document_id": document_id, "name": filename, "status": final_status}

    async def _upload_local(self, doc_id, storage_path, content, filename, size, content_type):
        from app.database.supabase_client import get_local_db
        # Save file to local filesystem
        full_path = os.path.join(settings.LOCAL_STORAGE_PATH, storage_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "wb") as f:
            f.write(content)
        # Save metadata to SQLite
        get_local_db().insert_document({
            "document_id": doc_id, "user_id": self.user_id, "name": filename,
            "storage_path": storage_path, "file_size": size,
            "file_type": content_type, "status": "processing",
        })

    async def _get_status(self, document_id: str) -> str:
        from app.database.supabase_client import get_local_db
        doc = get_local_db().get_document(document_id, self.user_id)
        return doc["status"] if doc else "processing"

    # ================================================================
    # Process Document
    # ================================================================
    async def _process_document(self, document_id: str, file_content: bytes, filename: str):
        """Extract text, chunk, embed, categorize."""
        try:
            processor = DocumentProcessor()
            chunks = await processor.process_document(file_content, filename, document_id, self.user_id)

            if not chunks:
                raise ValueError("No text could be extracted from the document.")

            logger.info(f"Created {len(chunks)} chunks for document {document_id}")

            # Store in Qdrant
            vector_store = VectorStore()
            await vector_store.store_chunks(chunks, document_id, self.user_id)

            # AI Categorization
            metadata, related_ids = await self._categorize(chunks, filename, document_id)

            max_page = max(c["page"] for c in chunks)
            update_data = {
                "status": "ready",
                "total_pages": max_page,
                "total_chunks": len(chunks),
                "processed_at": datetime.utcnow().isoformat(),
                "category": metadata["category"],
                "tags": metadata["tags"],
                "ai_summary": metadata["summary"],
                "key_entities": metadata["key_entities"],
                "related_document_ids": related_ids,
            }

            from app.database.supabase_client import get_local_db
            get_local_db().update_document(document_id, update_data)

            await get_connection_manager().broadcast_to_user(self.user_id, {
                "document_id": document_id, "status": "ready",
                "total_pages": max_page, "total_chunks": len(chunks),
                "category": metadata["category"], "tags": metadata["tags"],
            })

        except Exception as e:
            error_msg = str(e) if isinstance(e, ValueError) else f"Processing failed: {e}"
            logger.error(f"Error processing document {document_id}: {error_msg}", exc_info=True)

            from app.database.supabase_client import get_local_db
            get_local_db().update_document(document_id, {"status": "error", "error_message": error_msg})

            await get_connection_manager().broadcast_to_user(self.user_id, {
                "document_id": document_id, "status": "error", "error_message": error_msg,
            })
            if not isinstance(e, ValueError):
                raise

    async def _categorize(self, chunks, filename, document_id):
        try:
            from app.agents.categorization_agent import CategorizationAgent
            agent = CategorizationAgent()
            sample = " ".join(c["text"] for c in chunks[:5])
            metadata = await agent.categorize_document(sample, filename)
            related = await agent.find_related_documents(document_id, self.user_id, top_k=5)
            return metadata, related
        except Exception as e:
            logger.warning(f"Categorization failed for {document_id}: {e}")
            return {
                "category": "Other", "tags": [], "summary": f"Document: {filename}",
                "key_entities": {"people": [], "companies": [], "products": []},
            }, []

    # ================================================================
    # CRUD
    # ================================================================
    async def list_documents(self, skip: int = 0, limit: int = 20) -> tuple:
        from app.database.supabase_client import get_local_db
        docs_data, total = get_local_db().list_documents(self.user_id, skip, limit)
        documents = [Document(**d) for d in docs_data]
        return documents, total

    async def get_document(self, document_id: str) -> Optional[Document]:
        from app.database.supabase_client import get_local_db
        d = get_local_db().get_document(document_id, self.user_id)
        return Document(**d) if d else None

    async def delete_document(self, document_id: str) -> bool:
        document = await self.get_document(document_id)
        if not document:
            return False

        # Delete from Qdrant
        try:
            await VectorStore().delete_document_chunks(document_id, self.user_id)
        except Exception as e:
            logger.error(f"Error deleting from Qdrant: {e}")

        from app.database.supabase_client import get_local_db
        # Delete local file
        full_path = os.path.join(settings.LOCAL_STORAGE_PATH, document.storage_path)
        if os.path.exists(full_path):
            os.remove(full_path)
        get_local_db().delete_document(document_id, self.user_id)

        logger.info(f"Deleted document {document_id}")
        return True

    async def get_signed_url(self, document_id: str, expires_in: int = 3600) -> str:
        document = await self.get_document(document_id)
        if not document:
            raise ValueError("Document not found")

        # Return local file path (frontend can use /api/v1/documents/{id}/download)
        return f"/api/v1/documents/{document_id}/download"
