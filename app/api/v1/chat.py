"""
Chat and conversation endpoints.
Local SQLite mode only.
"""
import uuid
import re
import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from datetime import datetime
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.chat import (
    ChatMessageCreate, ChatMessageResponse,
    Conversation, ConversationUpdate,
    ConversationListResponse, ConversationDetailResponse,
    Message, Citation,
)
from app.services.rag_service import RAGService
from app.database.supabase_client import get_local_db

router = APIRouter()
logger = logging.getLogger(__name__)


def parse_datetime(dt_str):
    """Parse datetime string with robust error handling."""
    if not dt_str:
        return None
    dt_str = dt_str.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(dt_str)
    except ValueError:
        match = re.match(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\.(\d+)([+-]\d{2}:\d{2})", dt_str)
        if match:
            base, micro, tz = match.groups()
            micro = micro[:6].ljust(6, "0")
            try:
                return datetime.fromisoformat(f"{base}.{micro}{tz}")
            except ValueError:
                pass
        try:
            return datetime.fromisoformat(re.sub(r"\.\d+", "", dt_str))
        except ValueError:
            return datetime.now()


# ================================================================
# POST /message
# ================================================================
@router.post("/message", response_model=ChatMessageResponse, status_code=status.HTTP_201_CREATED)
async def create_chat_message(
    message_data: ChatMessageCreate,
    current_user: User = Depends(get_current_user),
):
    """Send a message and get RAG-powered response with citations."""
    conversation_id = message_data.conversation_id
    previous_message = None
    previous_topic = None
    previous_active_entity = None

    db = get_local_db()
    if not conversation_id:
        conversation_id = str(uuid.uuid4())
        db.insert_conversation({
            "conversation_id": conversation_id,
            "user_id": current_user.user_id,
            "title": message_data.message[:50],
        })
    else:
        conv = db.get_conversation(conversation_id, current_user.user_id)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        msgs = db.get_messages(conversation_id)
        if msgs:
            previous_message = msgs[-1].get("assistant_message")

    # Validate that all requested document_ids belong to the authenticated user
    if message_data.document_ids:
        for doc_id in message_data.document_ids:
            if not db.get_document(doc_id, current_user.user_id):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Document {doc_id} not found or not owned by you",
                )

    # RAG processing
    rag_service = RAGService()
    try:
        rag_result = await asyncio.wait_for(
            rag_service.answer_question(
                question=message_data.message,
                user_id=current_user.user_id,
                document_ids=message_data.document_ids,
                previous_message=previous_message,
                previous_topic=previous_topic,
                previous_active_entity=previous_active_entity,
            ),
            timeout=240.0,
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Request timed out. Try a simpler question.")

    # Save message + citations
    message_id = str(uuid.uuid4())
    message_record = {
        "message_id": message_id,
        "conversation_id": conversation_id,
        "user_message": message_data.message,
        "assistant_message": rag_result["answer"],
        "created_at": datetime.utcnow().isoformat(),
    }

    citation_records = [
        {
            "message_id": message_id,
            "document_id": c["document_id"],
            "chunk_id": f"chunk_{c['id']}",
            "page": c["page"],
            "start_char": c["start_char"],
            "end_char": c["end_char"],
            "text_snippet": c.get("text_snippet"),
        }
        for c in rag_result["citations"]
    ]

    db.insert_message(message_record)
    for cit in citation_records:
        db.insert_citation(cit)
    db.update_conversation(conversation_id, current_user.user_id, {})

    citations = [Citation(**c) for c in rag_result["citations"]]
    return ChatMessageResponse(
        message_id=message_id,
        conversation_id=conversation_id,
        answer=rag_result["answer"],
        citations=citations,
        created_at=datetime.utcnow(),
    )


# ================================================================
# GET /conversations
# ================================================================
@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    skip: int = 0, limit: int = 20,
    current_user: User = Depends(get_current_user),
):
    """List all conversations for the current user."""
    db = get_local_db()
    convs_data, total = db.list_conversations(current_user.user_id, skip, limit)
    conversations = []
    for c in convs_data:
        msgs = db.get_messages(c["conversation_id"])
        conversations.append(Conversation(
            conversation_id=c["conversation_id"],
            user_id=c["user_id"],
            title=c.get("title"),
            is_pinned=bool(c.get("is_pinned", False)),
            created_at=parse_datetime(c.get("created_at")) or datetime.now(),
            updated_at=parse_datetime(c.get("updated_at")) or datetime.now(),
            message_count=len(msgs),
        ))
    return ConversationListResponse(conversations=conversations, total=total)


# ================================================================
# GET /conversations/{id}
# ================================================================
@router.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
):
    """Get a specific conversation with all messages and citations."""
    db = get_local_db()
    conv = db.get_conversation(conversation_id, current_user.user_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    msgs_data = db.get_messages(conversation_id)
    messages = []
    for m in msgs_data:
        cits_data = db.get_citations(m["message_id"])
        citations = [
            Citation(
                id=i + 1,
                document_id=c["document_id"],
                document_name=c.get("document_name", "Document"),
                file_name=c.get("document_name", "Document"),
                page=c["page"],
                page_number=c["page"],
                start_char=c["start_char"],
                end_char=c["end_char"],
                quote=c.get("text_snippet"),
                text_snippet=c.get("text_snippet"),
            )
            for i, c in enumerate(cits_data)
        ]
        messages.append(Message(
            message_id=m["message_id"],
            conversation_id=m["conversation_id"],
            user_message=m["user_message"],
            assistant_message=m["assistant_message"],
            citations=citations,
            created_at=parse_datetime(m.get("created_at")) or datetime.now(),
        ))

    conversation = Conversation(
        conversation_id=conv["conversation_id"],
        user_id=conv["user_id"],
        title=conv.get("title"),
        is_pinned=bool(conv.get("is_pinned", False)),
        created_at=parse_datetime(conv.get("created_at")) or datetime.now(),
        updated_at=parse_datetime(conv.get("updated_at")) or datetime.now(),
        message_count=len(messages),
    )
    return ConversationDetailResponse(conversation=conversation, messages=messages)


# ================================================================
# DELETE /conversations/{id}
# ================================================================
@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
):
    """Delete a conversation and all its messages."""
    db = get_local_db()
    conv = db.get_conversation(conversation_id, current_user.user_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    db.delete_conversation(conversation_id, current_user.user_id)


# ================================================================
# PUT /conversations/{id}
# ================================================================
@router.put("/conversations/{conversation_id}", response_model=Conversation)
async def update_conversation(
    conversation_id: str,
    update_data: ConversationUpdate,
    current_user: User = Depends(get_current_user),
):
    """Update a conversation's title or pin status."""
    update_dict = {}
    if update_data.title is not None:
        update_dict["title"] = update_data.title
    if update_data.is_pinned is not None:
        update_dict["is_pinned"] = update_data.is_pinned

    db = get_local_db()
    conv = db.get_conversation(conversation_id, current_user.user_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    db.update_conversation(conversation_id, current_user.user_id, update_dict)
    updated = db.get_conversation(conversation_id, current_user.user_id)
    msgs = db.get_messages(conversation_id)
    return Conversation(
        conversation_id=updated["conversation_id"],
        user_id=updated["user_id"],
        title=updated.get("title"),
        is_pinned=bool(updated.get("is_pinned", False)),
        created_at=parse_datetime(updated.get("created_at")) or datetime.now(),
        updated_at=parse_datetime(updated.get("updated_at")) or datetime.now(),
        message_count=len(msgs),
    )
