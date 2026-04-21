"""
Knowledge Base API endpoints.
Provides categorized document browsing, filtering, and search.
Supports both Supabase and local SQLite modes.
"""
import json
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from app.database.supabase_client import get_supabase_client, is_local_mode, get_local_db
from app.models.document import Document
from app.middleware.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/knowledge-base", tags=["knowledge-base"])


@router.get("/categories")
async def list_categories(current_user: User = Depends(get_current_user)):
    """Get all categories with document counts."""
    user_id = current_user.user_id

    if is_local_mode():
        db = get_local_db()
        cats = db.get_categories(user_id)
        docs, _ = db.list_documents(user_id, 0, 9999)
        categories = [
            {"name": c["name"], "count": c["count"],
             "icon": get_category_icon(c["name"]),
             "color": get_category_color(c["name"])}
            for c in cats
        ]
        return {"categories": categories, "total": len(docs)}

    supabase = await get_supabase_client()
    result = supabase.table("documents").select("category").eq("user_id", user_id).eq("status", "ready").execute()
    category_counts = {}
    for doc in result.data:
        cat = doc.get("category") or "Other"
        category_counts[cat] = category_counts.get(cat, 0) + 1
    categories = [
        {"name": cat, "count": cnt, "icon": get_category_icon(cat), "color": get_category_color(cat)}
        for cat, cnt in sorted(category_counts.items())
    ]
    return {"categories": categories, "total": len(result.data)}


@router.get("/documents")
async def get_documents_by_filter(
    category: Optional[str] = None,
    tags: Optional[str] = Query(None, description="Comma-separated tags"),
    search: Optional[str] = None,
    skip: int = 0, limit: int = 20,
    current_user: User = Depends(get_current_user),
):
    """Get documents filtered by category, tags, or search query."""
    user_id = current_user.user_id

    if is_local_mode():
        db = get_local_db()
        all_docs, _ = db.list_documents(user_id, 0, 9999)
        # Filter
        filtered = [d for d in all_docs if d.get("status") == "ready"]
        if category:
            filtered = [d for d in filtered if d.get("category") == category]
        if tags:
            tag_set = {t.strip() for t in tags.split(",")}
            filtered = [d for d in filtered if tag_set & set(d.get("tags") or [])]
        if search:
            s = search.lower()
            filtered = [d for d in filtered if s in (d.get("name") or "").lower() or s in (d.get("ai_summary") or "").lower()]
        paginated = filtered[skip:skip + limit]
        documents = [Document(**d) for d in paginated]
        return {"documents": documents, "total": len(filtered)}

    supabase = await get_supabase_client()
    query = supabase.table("documents").select("*").eq("user_id", user_id).eq("status", "ready")
    if category:
        query = query.eq("category", category)
    if tags:
        tag_list = [t.strip() for t in tags.split(",")]
        query = query.overlaps("tags", tag_list)
    if search:
        query = query.or_(f"name.ilike.%{search}%,ai_summary.ilike.%{search}%")
    result = query.order("uploaded_at", desc=True).range(skip, skip + limit - 1).execute()
    documents = [Document(**doc) for doc in result.data]
    return {"documents": documents, "total": len(result.data)}


@router.get("/tags")
async def list_all_tags(current_user: User = Depends(get_current_user)):
    """Get all unique tags sorted by frequency."""
    user_id = current_user.user_id

    if is_local_mode():
        db = get_local_db()
        tags = db.get_tags(user_id)
        return {"tags": tags, "total": len(tags)}

    supabase = await get_supabase_client()
    result = supabase.table("documents").select("tags").eq("user_id", user_id).eq("status", "ready").execute()
    tag_counts = {}
    for doc in result.data:
        if doc.get("tags"):
            for tag in doc["tags"]:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
    sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)
    tags = [{"name": t, "count": c} for t, c in sorted_tags]
    return {"tags": tags, "total": len(tags)}


@router.get("/documents/{document_id}/related")
async def get_related_documents(
    document_id: str,
    current_user: User = Depends(get_current_user),
):
    """Get documents related to this one."""
    user_id = current_user.user_id

    if is_local_mode():
        db = get_local_db()
        doc = db.get_document(document_id, user_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        related_ids = doc.get("related_document_ids") or []
        if not related_ids:
            return {"documents": [], "total": 0}
        related = [db.get_document(rid, user_id) for rid in related_ids]
        documents = [Document(**d) for d in related if d]
        return {"documents": documents, "total": len(documents)}

    supabase = await get_supabase_client()
    doc_result = supabase.table("documents").select("related_document_ids").eq("document_id", document_id).eq("user_id", user_id).execute()
    if not doc_result.data:
        raise HTTPException(status_code=404, detail="Document not found")
    related_ids = doc_result.data[0].get("related_document_ids") or []
    if not related_ids:
        return {"documents": [], "total": 0}
    related_result = supabase.table("documents").select("*").in_("document_id", related_ids).eq("user_id", user_id).execute()
    documents = [Document(**doc) for doc in related_result.data]
    return {"documents": documents, "total": len(documents)}


def get_category_icon(category: str) -> str:
    icons = {
        "Legal": "scale", "Financial": "dollar-sign", "Product": "box",
        "Marketing": "megaphone", "HR": "users", "Operations": "settings",
        "Research": "book-open", "Other": "file",
    }
    return icons.get(category, "file")


def get_category_color(category: str) -> str:
    colors = {
        "Legal": "#3B82F6", "Financial": "#10B981", "Product": "#8B5CF6",
        "Marketing": "#F59E0B", "HR": "#EF4444", "Operations": "#6366F1",
        "Research": "#EC4899", "Other": "#6B7280",
    }
    return colors.get(category, "#6B7280")
