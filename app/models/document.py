"""
Document models.
"""
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime


class DocumentBase(BaseModel):
    """Base document model."""
    name: str
    file_size: int
    file_type: str = "application/pdf"


class DocumentCreate(DocumentBase):
    """Document creation model."""
    pass


class Document(DocumentBase):
    """Document model with ID and AI-generated metadata."""
    document_id: str
    user_id: str
    storage_path: str
    uploaded_at: datetime
    status: str = "processing"  # processing, ready, error
    total_pages: Optional[int] = None
    total_chunks: Optional[int] = None
    # AI-generated metadata
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    ai_summary: Optional[str] = None
    key_entities: Optional[Dict] = None
    related_document_ids: Optional[List[str]] = None
    
    class Config:
        from_attributes = True


class DocumentUploadResponse(BaseModel):
    """Response after document upload."""
    document_id: str
    name: str
    status: str
    message: str


class DocumentListResponse(BaseModel):
    """Response for document listing."""
    documents: List[Document]
    total: int




