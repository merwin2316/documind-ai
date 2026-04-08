"""
DocuMind AI — FastAPI application entry point.
"""
from fastapi import FastAPI, Request, status, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from app.api.v1 import router as api_v1_router
from app.middleware.auth import get_current_user
from app.models.user import User
from config import settings
from fastapi import WebSocket, WebSocketDisconnect
from app.services.websocket_manager import get_connection_manager
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="DocuMind AI API",
    description="RAG-powered document intelligence backend with citation support",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS — allow localhost in dev, production URL from env
allowed_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

if settings.FRONTEND_URL:
    allowed_origins.append(settings.FRONTEND_URL)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler — ensures CORS headers on errors."""
    logger.error(f"Unhandled exception: {type(exc).__name__}: {str(exc)}", exc_info=True)
    
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    if isinstance(exc, HTTPException):
        status_code = exc.status_code
        detail = exc.detail
    else:
        detail = "Internal server error"
    
    return JSONResponse(
        status_code=status_code,
        content={"detail": detail},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


# Include API routers
app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)


@app.websocket("/ws/documents/status")
async def websocket_document_status(websocket: WebSocket):
    """
    WebSocket endpoint for real-time document processing status updates.
    Client sends {"type": "auth", "token": "..."} as initial message.
    """
    manager = get_connection_manager()
    await websocket.accept()
    
    user_id = None
    try:
        auth_data = await websocket.receive_json()
        
        if auth_data.get("type") == "auth" and auth_data.get("token"):
            from app.middleware.auth import verify_token
            
            token = auth_data["token"]
            try:
                payload = await verify_token(token)
                user_id = payload.get("sub")
            except Exception as e:
                logger.warning(f"WebSocket authentication failed: {str(e)}")
                await websocket.close(code=1008, reason="Invalid token")
                return
                
            if user_id:
                await manager.register(websocket, user_id)
                logger.info(f"User {user_id} connected to document status WebSocket")
                
                try:
                    while True:
                        await websocket.receive_text()
                except WebSocketDisconnect:
                    manager.disconnect(websocket, user_id)
                except Exception as e:
                    logger.error(f"WebSocket connection error: {str(e)}")
                    manager.disconnect(websocket, user_id)
            else:
                await websocket.close(code=1008, reason="User ID missing in token")
        else:
            await websocket.close(code=1008, reason="Authentication required")
            
    except Exception as e:
        logger.error(f"WebSocket handler error: {str(e)}")
        if user_id:
            manager.disconnect(websocket, user_id)
        try:
            if websocket.client_state.name != "DISCONNECTED":
                await websocket.close(code=1011)
        except:
            pass


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "message": "DocuMind AI API is running",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    """Detailed health check."""
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT
    }


@app.post("/reset")
async def reset_all_data(current_user: User = Depends(get_current_user)):
    """
    Reset endpoint: Delete all files and conversations for the current user.
    
    **WARNING**: Permanently deletes all documents, conversations, messages,
    and citations for the authenticated user.
    """
    from app.database.supabase_client import get_supabase_client
    from app.services.vector_store import VectorStore
    
    supabase = await get_supabase_client()
    user_id = current_user.user_id
    vector_store = VectorStore()
    
    deleted_counts = {
        "documents": 0,
        "conversations": 0,
        "chunks": 0
    }
    
    try:
        # 1. Get all documents for user
        docs_result = supabase.table("documents").select("document_id").eq("user_id", user_id).execute()
        document_ids = [doc["document_id"] for doc in (docs_result.data or [])]
        deleted_counts["documents"] = len(document_ids)
        
        # 2. Delete all chunks from Qdrant
        for doc_id in document_ids:
            try:
                await vector_store.delete_document_chunks(doc_id, user_id)
                deleted_counts["chunks"] += 1
            except Exception as e:
                logger.warning(f"Error deleting chunks for document {doc_id}: {str(e)}")
        
        # 3. Delete documents from Supabase (cascades to pages)
        if document_ids:
            supabase.table("documents").delete().eq("user_id", user_id).execute()
        
        # 4. Delete conversations (cascades to messages and citations)
        convs_result = supabase.table("conversations").select("conversation_id").eq("user_id", user_id).execute()
        deleted_counts["conversations"] = len(convs_result.data or [])
        
        if deleted_counts["conversations"] > 0:
            supabase.table("conversations").delete().eq("user_id", user_id).execute()
        
        # 5. Delete files from Supabase Storage
        try:
            storage_files = supabase.storage.from_(settings.STORAGE_BUCKET).list()
            if storage_files:
                user_files = [f for f in storage_files if user_id in f.get("name", "")]
                for file in user_files:
                    try:
                        supabase.storage.from_(settings.STORAGE_BUCKET).remove([file["name"]])
                    except Exception as e:
                        logger.warning(f"Error deleting storage file {file['name']}: {str(e)}")
        except Exception as e:
            logger.warning(f"Error accessing storage: {str(e)}")
        
        logger.info(f"Reset completed for user {user_id}: {deleted_counts}")
        
        return {
            "message": "All data reset successfully",
            "deleted": deleted_counts
        }
        
    except Exception as e:
        logger.error(f"Error during reset: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error resetting data"
        )
