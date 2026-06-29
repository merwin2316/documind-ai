"""
DocuMind AI — FastAPI application entry point.
"""
from fastapi import FastAPI, Request, status, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from app.api.v1 import router as api_v1_router
from app.middleware.auth import get_current_user, DEV_USER_ID
from app.models.user import User
from config import settings
from fastapi import WebSocket, WebSocketDisconnect
from app.services.websocket_manager import get_connection_manager
import logging
import os

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
    Local mode: auto-authenticates with dev user.
    """
    manager = get_connection_manager()
    await websocket.accept()
    
    user_id = DEV_USER_ID
    try:
        # Wait for initial message (client still sends auth format for compatibility)
        auth_data = await websocket.receive_json()
        
        # In local mode, always accept and use dev user
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
    Local SQLite mode only.
    """
    from app.database.supabase_client import get_local_db
    from app.services.vector_store import VectorStore
    import shutil

    user_id = current_user.user_id
    vector_store = VectorStore()
    deleted_counts = {"documents": 0, "conversations": 0, "chunks": 0}

    try:
        db = get_local_db()
        docs, _ = db.list_documents(user_id)
        deleted_counts["documents"] = len(docs)

        for doc in docs:
            try:
                await vector_store.delete_document_chunks(doc["document_id"], user_id)
                deleted_counts["chunks"] += 1
            except Exception as e:
                logger.warning(f"Error deleting chunks: {e}")

        # Delete local files
        user_storage = os.path.join(settings.LOCAL_STORAGE_PATH, user_id)
        if os.path.exists(user_storage):
            shutil.rmtree(user_storage, ignore_errors=True)

        # Delete from SQLite
        import sqlite3
        conn = sqlite3.connect("./documind.db")
        convs = conn.execute("SELECT COUNT(*) FROM conversations WHERE user_id = ?", (user_id,)).fetchone()[0]
        deleted_counts["conversations"] = convs
        conn.execute("DELETE FROM messages WHERE conversation_id IN (SELECT conversation_id FROM conversations WHERE user_id = ?)", (user_id,))
        conn.execute("DELETE FROM conversations WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM document_chunks WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM citations WHERE document_id IN (SELECT document_id FROM documents WHERE user_id = ?)", (user_id,))
        conn.execute("DELETE FROM documents WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()

        logger.info(f"Reset completed for user {user_id}: {deleted_counts}")
        return {"message": "All data reset successfully", "deleted": deleted_counts}

    except Exception as e:
        logger.error(f"Error during reset: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error resetting data")
