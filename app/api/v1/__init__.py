"""
API v1 routes.
"""
from fastapi import APIRouter
from app.api.v1 import auth, documents, chat, chat_stream, knowledge_base

router = APIRouter()

# Include all v1 route modules
router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
router.include_router(documents.router, prefix="/documents", tags=["Documents"])
router.include_router(chat.router, prefix="/chat", tags=["Chat"])
router.include_router(chat_stream.router, prefix="/chat", tags=["Chat"])
router.include_router(knowledge_base.router, tags=["Knowledge Base"])
