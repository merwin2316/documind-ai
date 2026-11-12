"""
Chat streaming endpoints using Server-Sent Events (SSE).
Local SQLite mode only.
"""
import uuid
import json
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.chat import ChatMessageCreate
from app.services.rag_service import RAGService
from app.database.supabase_client import get_local_db

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/stream", status_code=status.HTTP_200_OK)
async def stream_chat_message(
    message_data: ChatMessageCreate,
    current_user: User = Depends(get_current_user)
):
    """
    Stream a chat response using Server-Sent Events (SSE).
    
    **Frontend Endpoint**: `POST /api/v1/chat/stream`
    
    **Response**: Text stream of events:
    - `event: status\ndata: "Analyzing..."`
    - `event: token\ndata: "The"`
    - `event: result\ndata: {"answer": "...", "citations": [...]}`
    """
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

    rag_service = RAGService()
    
    async def event_generator():
        # First yield the conversation ID so frontend knows where we are
        logger.info(f"Starting stream for conversation {conversation_id}")
        yield f"event: conversation_id\ndata: {conversation_id}\n\n"
        
        final_result = None
        
        try:
            async for event in rag_service.answer_question_stream(
                question=message_data.message,
                user_id=current_user.user_id,
                document_ids=message_data.document_ids,
                previous_message=previous_message,
                previous_topic=previous_topic,
                previous_active_entity=previous_active_entity
            ):
                event_type = event["type"]
                event_content = event.get("content")
                event_data = event.get("data")
                
                if event_type == "result":
                    final_result = event_data
                    # Don't yield result yet, save to DB first
                elif event_type == "token":
                    # Escape newlines for SSE data protocol
                    safe_content = json.dumps(event_content)
                    yield f"event: token\ndata: {safe_content}\n\n"
                elif event_type == "status":
                    yield f"event: status\ndata: {json.dumps(event_content)}\n\n"
            
            # Save to DB if we got a result
            if final_result:
                message_id = str(uuid.uuid4())
                message_record = {
                    "message_id": message_id,
                    "conversation_id": conversation_id,
                    "user_message": message_data.message,
                    "assistant_message": final_result["answer"],
                    "created_at": datetime.utcnow().isoformat(),
                }
                citations = final_result.get("citations", [])
                citation_records = [
                    {
                        "message_id": message_id,
                        "document_id": c["document_id"],
                        "chunk_id": c.get("chunk_id", f"chunk_{c.get('id', '')}"),
                        "page": c["page"],
                        "start_char": c["start_char"],
                        "end_char": c["end_char"],
                        "text_snippet": c.get("text_snippet"),
                    }
                    for c in citations
                ]

                db = get_local_db()
                db.insert_message(message_record)
                for cit in citation_records:
                    db.insert_citation(cit)
                db.update_conversation(conversation_id, current_user.user_id, {})
                
                # Yield final result to client
                final_payload = {
                    "message_id": message_id,
                    "conversation_id": conversation_id,
                    "answer": final_result["answer"],
                    "citations": citations,
                    "created_at": datetime.utcnow().isoformat()
                }
                yield f"event: result\ndata: {json.dumps(final_payload)}\n\n"
                
        except Exception as e:
            logger.error(f"Streaming error: {e}", exc_info=True)
            yield f"event: error\ndata: {json.dumps(str(e))}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
