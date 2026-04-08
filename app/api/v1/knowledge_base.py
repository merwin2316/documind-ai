"""
Knowledge Base API endpoints.
Provides categorized document browsing, filtering, and search.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from app.database.supabase_client import get_supabase_client
from app.models.document import Document
from app.middleware.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/knowledge-base", tags=["knowledge-base"])


@router.get("/categories")
async def list_categories(current_user: User = Depends(get_current_user)):
    """
    Get all categories with document counts.
    Returns list of categories and how many documents are in each.
    """
    supabase = await get_supabase_client()
    user_id = current_user.user_id
    
    # Get all documents with categories
    result = supabase.table("documents").select("category").eq(
        "user_id", user_id
    ).eq("status", "ready").execute()
    
    # Count documents per category
    category_counts = {}
    for doc in result.data:
        category = doc.get("category") or "Other"
        category_counts[category] = category_counts.get(category, 0) + 1
    
    # Format response
    categories = [
        {
            "name": category,
            "count": count,
            "icon": get_category_icon(category),
            "color": get_category_color(category)
        }
        for category, count in sorted(category_counts.items())
    ]
    
    return {"categories": categories, "total": len(result.data)}


@router.get("/documents")
async def get_documents_by_filter(
    category: Optional[str] = None,
    tags: Optional[str] = Query(None, description="Comma-separated tags"),
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_user)
):
    """
    Get documents filtered by category, tags, or search query.
    Supports multiple filters simultaneously.
    """
    supabase = await get_supabase_client()
    user_id = current_user.user_id
    
    # Build query
    query = supabase.table("documents").select("*").eq(
        "user_id", user_id
    ).eq("status", "ready")
    
    # Apply category filter
    if category:
        query = query.eq("category", category)
    
    # Apply tag filter (contains any of the tags)
    if tags:
        tag_list = [t.strip() for t in tags.split(",")]
        # Supabase: check if tags array overlaps with our tag list
        query = query.overlaps("tags", tag_list)
    
    # Apply search filter (search in name and summary)
    if search:
        query = query.or_(f"name.ilike.%{search}%,ai_summary.ilike.%{search}%")
    
    # Execute with pagination
    result = query.order("uploaded_at", desc=True).range(
        skip, skip + limit - 1
    ).execute()
    
    documents = [Document(**doc) for doc in result.data]
    
    return {"documents": documents, "total": len(result.data)}


@router.get("/tags")
async def list_all_tags(current_user: User = Depends(get_current_user)):
    """
    Get all unique tags across all documents.
    Returns tags sorted by frequency.
    """
    supabase = await get_supabase_client()
    user_id = current_user.user_id
    
    # Get all documents with tags
    result = supabase.table("documents").select("tags").eq(
        "user_id", user_id
    ).eq("status", "ready").execute()
    
    # Collect and count all tags
    tag_counts = {}
    for doc in result.data:
        if doc.get("tags"):
            for tag in doc["tags"]:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
    
    # Sort by frequency
    sorted_tags = sorted(
        tag_counts.items(), 
        key=lambda x: x[1], 
        reverse=True
    )
    
    tags = [
        {"name": tag, "count": count}
        for tag, count in sorted_tags
    ]
    
    return {"tags": tags, "total": len(tags)}


@router.get("/documents/{document_id}/related")
async def get_related_documents(
    document_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get documents related to this one.
    Uses AI-generated related document IDs.
    """
    supabase = await get_supabase_client()
    user_id = current_user.user_id
    
    # Get the document
    doc_result = supabase.table("documents").select(
        "related_document_ids"
    ).eq("document_id", document_id).eq("user_id", user_id).execute()
    
    if not doc_result.data:
        raise HTTPException(status_code=404, detail="Document not found")
    
    related_ids = doc_result.data[0].get("related_document_ids") or []
    
    if not related_ids:
        return {"documents": [], "total": 0}
    
    # Get related documents
    related_result = supabase.table("documents").select("*").in_(
        "document_id", related_ids
    ).eq("user_id", user_id).execute()
    
    documents = [Document(**doc) for doc in related_result.data]
    
    return {"documents": documents, "total": len(documents)}


def get_category_icon(category: str) -> str:
    """Get icon name for category."""
    icons = {
        "Legal": "scale",
        "Financial": "dollar-sign",
        "Product": "box",
        "Marketing": "megaphone",
        "HR": "users",
        "Operations": "settings",
        "Research": "book-open",
        "Other": "file"
    }
    return icons.get(category, "file")


def get_category_color(category: str) -> str:
    """Get color code for category."""
    colors = {
        "Legal": "#3B82F6",
        "Financial": "#10B981",
        "Product": "#8B5CF6",
        "Marketing": "#F59E0B",
        "HR": "#EF4444",
        "Operations": "#6366F1",
        "Research": "#EC4899",
        "Other": "#6B7280"
    }
    return colors.get(category, "#6B7280")
