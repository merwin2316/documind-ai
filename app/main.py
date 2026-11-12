"""
DocuMind AI — FastAPI application entry point.
"""
from fastapi import FastAPI, Request, status, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from app.api.v1 import router as api_v1_router
from app.middleware.auth import get_current_user, verify_jwt_token, DEV_USER_ID
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
    Enforces initial message-based authentication (bearer tokens in query params are strictly prohibited).
    """
    import asyncio
    manager = get_connection_manager()
    await websocket.accept()
    
    user_id = None
    try:
        # Require initial JSON auth frame within 5 seconds
        try:
            auth_frame = await asyncio.wait_for(websocket.receive_json(), timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning("WebSocket connection timed out waiting for authentication frame")
            try:
                await websocket.send_json({"type": "error", "message": "Authentication timeout"})
                await websocket.close(code=1008)
            except Exception:
                pass
            return
        except Exception:
            logger.warning("WebSocket initial frame was not valid JSON")
            try:
                await websocket.close(code=1008)
            except Exception:
                pass
            return

        if not isinstance(auth_frame, dict) or auth_frame.get("type") != "auth":
            logger.warning("WebSocket initial frame missing 'type': 'auth'")
            try:
                await websocket.send_json({"type": "error", "message": "First message must be an auth frame"})
                await websocket.close(code=1008)
            except Exception:
                pass
            return

        token = auth_frame.get("token")
        if not token or not isinstance(token, str) or not token.strip():
            logger.warning("WebSocket auth frame missing token")
            try:
                await websocket.send_json({"type": "error", "message": "Authentication token required"})
                await websocket.close(code=1008)
            except Exception:
                pass
            return

        try:
            claims = verify_jwt_token(token)
            user_id = claims["user_id"]
        except HTTPException as e:
            logger.warning(f"WebSocket authentication failed: {e.detail}")
            try:
                await websocket.send_json({"type": "error", "message": "Authentication failed"})
                await websocket.close(code=1008)
            except Exception:
                pass
            return
        except Exception as e:
            logger.warning(f"WebSocket authentication error: {type(e).__name__}")
            try:
                await websocket.send_json({"type": "error", "message": "Authentication failed"})
                await websocket.close(code=1008)
            except Exception:
                pass
            return

        # Register connection for verified user ONLY
        await manager.register(websocket, user_id)
        await websocket.send_json({"type": "authenticated", "user_id": user_id})
        logger.info(f"Verified user {user_id} connected to document status WebSocket")
        
        try:
            while True:
                msg = await websocket.receive_text()
                if msg == "ping":
                    await websocket.send_text("pong")
        except WebSocketDisconnect:
            manager.disconnect(websocket, user_id)
        except Exception as e:
            logger.debug(f"WebSocket disconnect: {type(e).__name__}")
            manager.disconnect(websocket, user_id)
            
    except Exception as e:
        logger.warning(f"WebSocket handler error: {type(e).__name__}")
        if user_id:
            manager.disconnect(websocket, user_id)
        try:
            if websocket.client_state.name != "DISCONNECTED":
                await websocket.close(code=1011)
        except Exception:
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
    Strictly restricted: disabled by default, requires explicit ENABLE_RESET_ENDPOINT=True in development.
    """
    if not settings.ENABLE_RESET_ENDPOINT or settings.ENVIRONMENT != "development":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Reset endpoint is disabled in this environment."
        )
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
