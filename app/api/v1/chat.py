"""
Chat and conversation endpoints.
"""
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from datetime import datetime
import re
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.chat import (
    ChatMessageCreate,
    ChatMessageResponse,
    Conversation,
    ConversationUpdate,
    ConversationListResponse,
    ConversationDetailResponse,
    Message,
    Citation
)
from app.services.rag_service import RAGService
from app.database.supabase_client import get_supabase_client

router = APIRouter()


def parse_datetime(dt_str):
    """Parse datetime string with robust error handling for various ISO formats."""
    if not dt_str:
        return None
    # Normalize: replace Z with +00:00
    dt_str = dt_str.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(dt_str)
    except ValueError:
        # Handle microseconds with variable length
        # Pattern: YYYY-MM-DDTHH:MM:SS.microseconds+tz
        match = re.match(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\.(\d+)([+-]\d{2}:\d{2})', dt_str)
        if match:
            base, microsec, tz = match.groups()
            # Truncate microseconds to 6 digits (max supported)
            microsec = microsec[:6].ljust(6, '0')[:6]  # Pad or truncate to 6
            dt_str = f"{base}.{microsec}{tz}"
            try:
                return datetime.fromisoformat(dt_str)
            except ValueError:
                pass
        # Fallback: try without microseconds
        try:
            dt_str_no_micro = re.sub(r'\.\d+', '', dt_str)
            return datetime.fromisoformat(dt_str_no_micro)
        except ValueError:
            return datetime.now()


@router.post("/message", response_model=ChatMessageResponse, status_code=status.HTTP_201_CREATED)
async def create_chat_message(
    message_data: ChatMessageCreate,
    current_user: User = Depends(get_current_user)
):
    """
    Send a message and get RAG-powered response with citations.
    
    **Frontend Endpoint**: `POST /api/v1/chat/message`
    
    **Headers**: 
    - `Authorization: Bearer <jwt_token>`
    - `Content-Type: application/json`
    
    **Request Body**:
    ```json
    {
        "conversation_id": "uuid" | null,  // null creates new conversation
        "message": "What does the NDA say about data sharing?",
        "document_ids": ["uuid1", "uuid2"] | null  // optional: filter to specific documents
    }
    ```
    
    **Response**:
    ```json
    {
        "message_id": "uuid",
        "conversation_id": "uuid",
        "answer": "The NDA restricts data sharing... [CITATION 1]",
        "citations": [
            {
                "id": 1,
                "document_id": "uuid",
                "document_name": "NDA.pdf",
                "page": 3,
                "start_char": 120,
                "end_char": 280,
                "text_snippet": "The company shall not disclose..."
            }
        ],
        "created_at": "2024-01-01T00:00:00Z"
    }
    ```
    """
    supabase = await get_supabase_client()
    
    # Get or create conversation
    conversation_id = message_data.conversation_id
    if not conversation_id:
        # Create new conversation
        conversation_id = str(uuid.uuid4())
        title = message_data.message[:50]  # Use first 50 chars as title
        
        supabase.table("conversations").insert({
            "conversation_id": conversation_id,
            "user_id": current_user.user_id,
            "title": title
        }).execute()
    else:
        # Verify conversation belongs to user
        conv_result = supabase.table("conversations").select("*").eq("conversation_id", conversation_id).eq("user_id", current_user.user_id).execute()
        if not conv_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )
    
    # Get previous assistant message and conversation state for follow-up detection and coreference
    previous_message = None
    previous_topic = None
    previous_active_entity = None
    if conversation_id:
        # Get last assistant message from this conversation
        last_msg = supabase.table("messages").select("assistant_message").eq("conversation_id", conversation_id).order("created_at", desc=True).limit(1).execute()
        if last_msg.data and len(last_msg.data) > 0:
            previous_message = last_msg.data[0].get("assistant_message")
        
        # Get conversation metadata for topic and active_entity tracking
        # Topic and Active Entity columns missing in DB, so we passing None
        previous_topic = None
        previous_active_entity = None
    
    # Get RAG answer with timeout protection
    import asyncio
    import logging
    logger = logging.getLogger(__name__)
    
    rag_service = RAGService()
    try:
        logger.info(f"Starting RAG processing for question: {message_data.message[:100]}")
        # Use asyncio.wait_for to add an overall timeout (4 minutes)
        rag_result = await asyncio.wait_for(
            rag_service.answer_question(
                question=message_data.message,
                user_id=current_user.user_id,
                document_ids=message_data.document_ids,
                previous_message=previous_message,
                previous_topic=previous_topic,
                previous_active_entity=previous_active_entity
            ),
            timeout=240.0  # 4 minutes total timeout for RAG processing
        )
        logger.info("RAG processing completed successfully")
    except asyncio.TimeoutError:
        logger.error("RAG processing timed out after 4 minutes")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Request took too long to process. Please try a simpler question or try again later."
        )
    
    # Create message record
    message_id = str(uuid.uuid4())
    message_record = {
        "message_id": message_id,
        "conversation_id": conversation_id,
        "user_message": message_data.message,
        "assistant_message": rag_result["answer"],
        "created_at": datetime.utcnow().isoformat()
    }
    
    supabase.table("messages").insert(message_record).execute()
    
    # Store citations
    if rag_result["citations"]:
        citation_records = [
            {
                "message_id": message_id,
                "document_id": cit["document_id"],
                "chunk_id": f"chunk_{cit['id']}",  # Reference to Qdrant chunk
                "page": cit["page"],
                "start_char": cit["start_char"],
                "end_char": cit["end_char"],
                "text_snippet": cit.get("text_snippet")
            }
            for cit in rag_result["citations"]
        ]
        supabase.table("citations").insert(citation_records).execute()
    
    # Update conversation timestamp and metadata (topic, active_entity)
    update_data = {
        "updated_at": datetime.utcnow().isoformat()
    }
    
    supabase.table("conversations").update({
        "updated_at": datetime.utcnow().isoformat()
    }).eq("conversation_id", conversation_id).execute()
    
    # Format citations for response
    citations = [
        Citation(**cit) for cit in rag_result["citations"]
    ]
    
    return ChatMessageResponse(
        message_id=message_id,
        conversation_id=conversation_id,
        answer=rag_result["answer"],
        citations=citations,
        created_at=datetime.utcnow()
    )


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_user)
):
    """
    List all conversations for the current user.
    
    **Frontend Endpoint**: `GET /api/v1/chat/conversations?skip=0&limit=20`
    
    **Headers**: 
    - `Authorization: Bearer <jwt_token>`
    
    **Query Parameters**:
    - `skip`: Number of conversations to skip (default: 0)
    - `limit`: Maximum number of conversations to return (default: 20)
    
    **Response**:
    ```json
    {
        "conversations": [
            {
                "conversation_id": "uuid",
                "title": "What does the NDA say...",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
                "message_count": 5
            }
        ],
        "total": 1
    }
    ```
    """
    supabase = await get_supabase_client()
    
    # Get conversations - optimized: don't fetch message counts in list view (not needed for sidebar)
    result = supabase.table("conversations").select("*").eq("user_id", current_user.user_id).order("updated_at", desc=True).range(skip, skip + limit - 1).execute()
    
    # OPTIMIZED: Get message counts for all conversations in a single batch query
    # Instead of N queries (one per conversation), we fetch all messages for all conversations at once
    conversation_ids = [conv["conversation_id"] for conv in result.data]
    message_counts = {}
    
    if conversation_ids:
        # Single query to get all messages for all conversations (much faster than N queries)
        # We only need conversation_id, so we can use a minimal select
        try:
            all_messages = supabase.table("messages").select("conversation_id").in_("conversation_id", conversation_ids).execute()
            
            # Count messages per conversation in Python (single query + in-memory counting)
            # This is O(n) where n = total messages, much better than N queries
            for msg in (all_messages.data or []):
                conv_id = msg.get("conversation_id")
                if conv_id:
                    message_counts[conv_id] = message_counts.get(conv_id, 0) + 1
        except Exception as e:
            # If batch query fails (e.g., too many IDs), fall back to 0 counts
            # Log warning but don't fail the entire request
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to batch fetch message counts: {str(e)}")
            # Set all counts to 0 as fallback
            message_counts = {conv_id: 0 for conv_id in conversation_ids}
    
    conversations = []
    for conv_data in result.data:
        conv_id = conv_data["conversation_id"]
        message_count = message_counts.get(conv_id, 0)
        
        # Parse datetime strings
        created_at = parse_datetime(conv_data.get("created_at"))
        updated_at = parse_datetime(conv_data.get("updated_at"))
        
        conversations.append(Conversation(
            conversation_id=conv_id,
            user_id=conv_data["user_id"],
            title=conv_data.get("title"),
            is_pinned=conv_data.get("is_pinned", False),
            created_at=created_at or datetime.now(),
            updated_at=updated_at or datetime.now(),
            message_count=message_count
        ))
    
    # Get total count
    count_result = supabase.table("conversations").select("*", count="exact").eq("user_id", current_user.user_id).execute()
    total = count_result.count if hasattr(count_result, 'count') else 0
    
    return ConversationListResponse(
        conversations=conversations,
        total=total
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific conversation with all messages and citations.
    
    **Frontend Endpoint**: `GET /api/v1/chat/conversations/{conversation_id}`
    
    **Headers**: 
    - `Authorization: Bearer <jwt_token>`
    
    **Response**:
    ```json
    {
        "conversation": {
            "conversation_id": "uuid",
            "title": "What does the NDA say...",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
            "message_count": 2
        },
        "messages": [
            {
                "message_id": "uuid",
                "conversation_id": "uuid",
                "user_message": "What does the NDA say?",
                "assistant_message": "The NDA says... [CITATION 1]",
                "citations": [
                    {
                        "id": 1,
                        "document_id": "uuid",
                        "document_name": "NDA.pdf",
                        "page": 3,
                        "start_char": 120,
                        "end_char": 280
                    }
                ],
                "created_at": "2024-01-01T00:00:00Z"
            }
        ]
    }
    ```
    """
    supabase = await get_supabase_client()
    
    # Verify conversation belongs to user
    conv_result = supabase.table("conversations").select("*").eq("conversation_id", conversation_id).eq("user_id", current_user.user_id).execute()
    
    if not conv_result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    conv_data = conv_result.data[0]
    
    # Get messages
    messages_result = supabase.table("messages").select("*").eq("conversation_id", conversation_id).order("created_at", desc=False).execute()
    
    messages = []
    
    # Fetch all citations for this conversation in one go to avoid N+1 queries
    # Get all message IDs
    message_ids = [msg["message_id"] for msg in messages_result.data]
    
    citations_by_message = {}
    document_names = {}
    
    if message_ids:
        # Get all citations
        all_citations_result = supabase.table("citations").select("*").in_("message_id", message_ids).execute()
        
        # Group by message_id
        for cit in (all_citations_result.data or []):
            msg_id = cit["message_id"]
            if msg_id not in citations_by_message:
                citations_by_message[msg_id] = []
            citations_by_message[msg_id].append(cit)
            
        # Get all document IDs from citations
        doc_ids = list(set([cit["document_id"] for cit in (all_citations_result.data or [])]))
        
        if doc_ids:
            docs_result = supabase.table("documents").select("document_id, name").in_("document_id", doc_ids).execute()
            document_names = {doc["document_id"]: doc["name"] for doc in docs_result.data}
    
    for msg_data in messages_result.data:
        # Get citations for this message from pre-fetched map
        msg_citations = citations_by_message.get(msg_data["message_id"], [])
        
        citations = [
            Citation(
                id=idx + 1,
                document_id=cit["document_id"],
                document_name=document_names.get(cit["document_id"], "Unknown Document"),
                file_name=document_names.get(cit["document_id"], "Unknown Document"),
                page=cit["page"],
                page_number=cit["page"],
                start_char=cit["start_char"],
                end_char=cit["end_char"],
                quote=cit.get("text_snippet"),
                text_snippet=cit.get("text_snippet")
            )
            for idx, cit in enumerate(msg_citations)
        ]
        
        # Parse datetime string
        msg_created_at = parse_datetime(msg_data.get("created_at"))
        
        messages.append(Message(
            message_id=msg_data["message_id"],
            conversation_id=msg_data["conversation_id"],
            user_message=msg_data["user_message"],
            assistant_message=msg_data["assistant_message"],
            citations=citations,
            created_at=msg_created_at or datetime.now()
        ))
    
    # Get message count
    msg_count_result = supabase.table("messages").select("*", count="exact").eq("conversation_id", conversation_id).execute()
    message_count = msg_count_result.count if hasattr(msg_count_result, 'count') else 0
    
    # Parse datetime strings
    conv_created_at = parse_datetime(conv_data.get("created_at"))
    conv_updated_at = parse_datetime(conv_data.get("updated_at"))
    
    conversation = Conversation(
        conversation_id=conv_data["conversation_id"],
        user_id=conv_data["user_id"],
        title=conv_data.get("title"),
        is_pinned=conv_data.get("is_pinned", False),
        created_at=conv_created_at or datetime.now(),
        updated_at=conv_updated_at or datetime.now(),
        message_count=message_count
    )
    
    return ConversationDetailResponse(
        conversation=conversation,
        messages=messages
    )


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Delete a conversation and all its messages.
    
    **Frontend Endpoint**: `DELETE /api/v1/chat/conversations/{conversation_id}`
    
    **Headers**: 
    - `Authorization: Bearer <jwt_token>`
    
    **Response**: 204 No Content
    """
    supabase = await get_supabase_client()
    
    # Verify conversation belongs to user
    conv_result = supabase.table("conversations").select("*").eq("conversation_id", conversation_id).eq("user_id", current_user.user_id).execute()
    
    if not conv_result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    # Delete conversation (cascades to messages and citations)
    supabase.table("conversations").delete().eq("conversation_id", conversation_id).eq("user_id", current_user.user_id).execute()


@router.put("/conversations/{conversation_id}", response_model=Conversation)
async def update_conversation(
    conversation_id: str,
    update_data: ConversationUpdate,
    current_user: User = Depends(get_current_user)
):
    """
    Update a conversation's title or pin status.
    
    **Frontend Endpoint**: `PUT /api/v1/chat/conversations/{conversation_id}`
    
    **Headers**: 
    - `Authorization: Bearer <jwt_token>`
    
    **Request Body**:
    ```json
    {
        "title": "New conversation title",  // optional
        "is_pinned": true  // optional
    }
    ```
    
    **Response**: Updated Conversation object
    """
    supabase = await get_supabase_client()
    
    # Verify conversation belongs to user
    conv_result = supabase.table("conversations").select("*").eq("conversation_id", conversation_id).eq("user_id", current_user.user_id).execute()
    
    if not conv_result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    # Build update dict with only provided fields
    update_dict = {"updated_at": datetime.utcnow().isoformat()}
    
    if update_data.title is not None:
        update_dict["title"] = update_data.title
    
    if update_data.is_pinned is not None:
        update_dict["is_pinned"] = update_data.is_pinned
    
    # Update conversation
    result = supabase.table("conversations").update(update_dict).eq("conversation_id", conversation_id).eq("user_id", current_user.user_id).execute()
    
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update conversation"
        )
    
    updated_conv = result.data[0]
    
    # Get message count
    msg_count_result = supabase.table("messages").select("*", count="exact").eq("conversation_id", conversation_id).execute()
    message_count = msg_count_result.count if hasattr(msg_count_result, 'count') else 0
    
    # Parse datetime strings
    created_at = parse_datetime(updated_conv.get("created_at"))
    updated_at = parse_datetime(updated_conv.get("updated_at"))
    
    return Conversation(
        conversation_id=updated_conv["conversation_id"],
        user_id=updated_conv["user_id"],
        title=updated_conv.get("title"),
        is_pinned=updated_conv.get("is_pinned", False),
        created_at=created_at or datetime.now(),
        updated_at=updated_at or datetime.now(),
        message_count=message_count
    )
