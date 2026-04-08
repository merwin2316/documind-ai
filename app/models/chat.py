"""
Chat and conversation models.
"""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class Citation(BaseModel):
    """Citation model for RAG responses with ChatGPT-style citation support."""
    id: int
    document_id: str
    document_name: str
    file_name: Optional[str] = None  # Alias for document_name (for frontend)
    page: int
    page_number: Optional[int] = None  # Alias for page (for frontend)
    start_char: int
    end_char: int
    quote: Optional[str] = None  # Quote text for highlighting
    text_snippet: Optional[str] = None  # Backward compatibility
    chunk_id: Optional[str] = None  # Reference to chunk
    bbox: Optional[List] = None  # Optional: bounding boxes for precise highlighting
    
    def __init__(self, **data):
        # Set aliases if not provided
        if "file_name" not in data and "document_name" in data:
            data["file_name"] = data["document_name"]
        if "page_number" not in data and "page" in data:
            data["page_number"] = data["page"]
        if "quote" not in data and "text_snippet" in data:
            data["quote"] = data["text_snippet"]
        super().__init__(**data)


class ChatMessageCreate(BaseModel):
    """Request model for creating a chat message."""
    conversation_id: Optional[str] = None  # If None, creates new conversation
    message: str
    document_ids: Optional[List[str]] = None  # Optional: filter to specific documents


class ChatMessageResponse(BaseModel):
    """Response model for chat message."""
    message_id: str
    conversation_id: str
    answer: str
    citations: List[Citation]
    created_at: datetime


class Conversation(BaseModel):
    """Conversation model."""
    conversation_id: str
    user_id: str
    title: Optional[str] = None
    is_pinned: Optional[bool] = False
    created_at: datetime
    updated_at: datetime
    message_count: Optional[int] = 0
    
    class Config:
        from_attributes = True


class ConversationUpdate(BaseModel):
    """Request model for updating a conversation."""
    title: Optional[str] = None
    is_pinned: Optional[bool] = None


class ConversationListResponse(BaseModel):
    """Response for conversation listing."""
    conversations: List[Conversation]
    total: int


class Message(BaseModel):
    """Message model."""
    message_id: str
    conversation_id: str
    user_message: str
    assistant_message: str
    citations: List[Citation]
    created_at: datetime
    
    class Config:
        from_attributes = True


class ConversationDetailResponse(BaseModel):
    """Detailed conversation with messages."""
    conversation: Conversation
    messages: List[Message]




