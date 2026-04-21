"""
Chat and conversation endpoints.
Supports both Supabase and local SQLite modes.
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
from app.database.supabase_client import get_supabase_client, is_local_mode, get_local_db

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

    if is_local_mode():
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
    else:
        supabase = await get_supabase_client()
        if not conversation_id:
            conversation_id = str(uuid.uuid4())
            supabase.table("conversations").insert({
                "conversation_id": conversation_id,
                "user_id": current_user.user_id,
                "title": message_data.message[:50],
            }).execute()
        else:
            conv_result = supabase.table("conversations").select("*").eq("conversation_id", conversation_id).eq("user_id", current_user.user_id).execute()
            if not conv_result.data:
                raise HTTPException(status_code=404, detail="Conversation not found")
        if conversation_id:
            last_msg = supabase.table("messages").select("assistant_message").eq("conversation_id", conversation_id).order("created_at", desc=True).limit(1).execute()
            if last_msg.data:
                previous_message = last_msg.data[0].get("assistant_message")

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

    if is_local_mode():
        db = get_local_db()
        db.insert_message(message_record)
        for cit in citation_records:
            db.insert_citation(cit)
        db.update_conversation(conversation_id, current_user.user_id, {})
    else:
        supabase = await get_supabase_client()
        supabase.table("messages").insert(message_record).execute()
        if citation_records:
            supabase.table("citations").insert(citation_records).execute()
        supabase.table("conversations").update({"updated_at": datetime.utcnow().isoformat()}).eq("conversation_id", conversation_id).execute()

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
    if is_local_mode():
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

    # Supabase mode
    supabase = await get_supabase_client()
    result = supabase.table("conversations").select("*").eq("user_id", current_user.user_id).order("updated_at", desc=True).range(skip, skip + limit - 1).execute()

    conversation_ids = [c["conversation_id"] for c in result.data]
    message_counts = {}
    if conversation_ids:
        try:
            all_msgs = supabase.table("messages").select("conversation_id").in_("conversation_id", conversation_ids).execute()
            for m in (all_msgs.data or []):
                cid = m.get("conversation_id")
                if cid:
                    message_counts[cid] = message_counts.get(cid, 0) + 1
        except Exception:
            message_counts = {cid: 0 for cid in conversation_ids}

    conversations = []
    for c in result.data:
        conversations.append(Conversation(
            conversation_id=c["conversation_id"],
            user_id=c["user_id"],
            title=c.get("title"),
            is_pinned=c.get("is_pinned", False),
            created_at=parse_datetime(c.get("created_at")) or datetime.now(),
            updated_at=parse_datetime(c.get("updated_at")) or datetime.now(),
            message_count=message_counts.get(c["conversation_id"], 0),
        ))

    count_result = supabase.table("conversations").select("*", count="exact").eq("user_id", current_user.user_id).execute()
    total = count_result.count if hasattr(count_result, "count") else 0
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
    if is_local_mode():
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

    # Supabase mode
    supabase = await get_supabase_client()
    conv_result = supabase.table("conversations").select("*").eq("conversation_id", conversation_id).eq("user_id", current_user.user_id).execute()
    if not conv_result.data:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conv_data = conv_result.data[0]
    messages_result = supabase.table("messages").select("*").eq("conversation_id", conversation_id).order("created_at", desc=False).execute()

    message_ids = [m["message_id"] for m in messages_result.data]
    citations_by_message = {}
    document_names = {}

    if message_ids:
        all_cits = supabase.table("citations").select("*").in_("message_id", message_ids).execute()
        for c in (all_cits.data or []):
            mid = c["message_id"]
            citations_by_message.setdefault(mid, []).append(c)
        doc_ids = list({c["document_id"] for c in (all_cits.data or [])})
        if doc_ids:
            docs = supabase.table("documents").select("document_id, name").in_("document_id", doc_ids).execute()
            document_names = {d["document_id"]: d["name"] for d in docs.data}

    messages = []
    for m in messages_result.data:
        msg_cits = citations_by_message.get(m["message_id"], [])
        citations = [
            Citation(
                id=i + 1,
                document_id=c["document_id"],
                document_name=document_names.get(c["document_id"], "Unknown"),
                file_name=document_names.get(c["document_id"], "Unknown"),
                page=c["page"],
                page_number=c["page"],
                start_char=c["start_char"],
                end_char=c["end_char"],
                quote=c.get("text_snippet"),
                text_snippet=c.get("text_snippet"),
            )
            for i, c in enumerate(msg_cits)
        ]
        messages.append(Message(
            message_id=m["message_id"],
            conversation_id=m["conversation_id"],
            user_message=m["user_message"],
            assistant_message=m["assistant_message"],
            citations=citations,
            created_at=parse_datetime(m.get("created_at")) or datetime.now(),
        ))

    msg_count = supabase.table("messages").select("*", count="exact").eq("conversation_id", conversation_id).execute()

    conversation = Conversation(
        conversation_id=conv_data["conversation_id"],
        user_id=conv_data["user_id"],
        title=conv_data.get("title"),
        is_pinned=conv_data.get("is_pinned", False),
        created_at=parse_datetime(conv_data.get("created_at")) or datetime.now(),
        updated_at=parse_datetime(conv_data.get("updated_at")) or datetime.now(),
        message_count=msg_count.count if hasattr(msg_count, "count") else 0,
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
    if is_local_mode():
        db = get_local_db()
        conv = db.get_conversation(conversation_id, current_user.user_id)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        db.delete_conversation(conversation_id, current_user.user_id)
        return

    supabase = await get_supabase_client()
    conv_result = supabase.table("conversations").select("*").eq("conversation_id", conversation_id).eq("user_id", current_user.user_id).execute()
    if not conv_result.data:
        raise HTTPException(status_code=404, detail="Conversation not found")
    supabase.table("conversations").delete().eq("conversation_id", conversation_id).eq("user_id", current_user.user_id).execute()


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

    if is_local_mode():
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

    supabase = await get_supabase_client()
    conv_result = supabase.table("conversations").select("*").eq("conversation_id", conversation_id).eq("user_id", current_user.user_id).execute()
    if not conv_result.data:
        raise HTTPException(status_code=404, detail="Conversation not found")

    update_dict["updated_at"] = datetime.utcnow().isoformat()
    result = supabase.table("conversations").update(update_dict).eq("conversation_id", conversation_id).eq("user_id", current_user.user_id).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to update conversation")

    u = result.data[0]
    msg_count = supabase.table("messages").select("*", count="exact").eq("conversation_id", conversation_id).execute()
    return Conversation(
        conversation_id=u["conversation_id"],
        user_id=u["user_id"],
        title=u.get("title"),
        is_pinned=u.get("is_pinned", False),
        created_at=parse_datetime(u.get("created_at")) or datetime.now(),
        updated_at=parse_datetime(u.get("updated_at")) or datetime.now(),
        message_count=msg_count.count if hasattr(msg_count, "count") else 0,
    )
