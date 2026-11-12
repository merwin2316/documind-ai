"""
Document upload and management endpoints.
"""
import uuid
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from typing import List
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.document import Document, DocumentUploadResponse, DocumentListResponse
from app.services.document_service import DocumentService
from app.services.document_processor import DocumentProcessor

router = APIRouter()


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """
    Upload a document for processing (PDF or DOCX).
    
    **Frontend Endpoint**: `POST /api/v1/documents/upload`
    
    **Headers**: 
    - `Content-Type: multipart/form-data`
    
    **Request Body**:
    - `file`: PDF or DOCX file (multipart/form-data)
    
    **Response**:
    ```json
    {
        "document_id": "uuid",
        "name": "document.pdf",
        "status": "processing",
        "message": "Document uploaded successfully"
    }
    ```
    
    **Note**: Processing happens asynchronously. Use GET /documents/{document_id} to check status.
    """
    # Validate file type
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required"
        )
    
    file_ext = file.filename.lower()
    if not (file_ext.endswith('.pdf') or file_ext.endswith('.docx')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF and DOCX files are supported"
        )
    
    # Check file size (e.g., 10MB limit)
    file_content = await file.read()
    file_size = len(file_content)
    
    if file_size > 10 * 1024 * 1024:  # 10MB
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds 10MB limit"
        )
    
    # Reset file pointer
    await file.seek(0)
    
    # Upload and process document
    document_service = DocumentService(current_user.user_id)
    result = await document_service.upload_and_process(file, file.filename, file_size)
    
    return DocumentUploadResponse(
        document_id=result["document_id"],
        name=result["name"],
        status=result["status"],
        message="Document uploaded successfully. Processing in background."
    )


@router.get("", response_model=DocumentListResponse, include_in_schema=False)
@router.get("/", response_model=DocumentListResponse)
async def list_documents(
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_user)
):
    """
    List all documents for the current user.
    
    **Frontend Endpoint**: `GET /api/v1/documents?skip=0&limit=20`
    
    **Query Parameters**:
    - `skip`: Number of documents to skip (default: 0)
    - `limit`: Maximum number of documents to return (default: 20)
    
    **Response**:
    ```json
    {
        "documents": [
            {
                "document_id": "uuid",
                "name": "document.pdf",
                "status": "ready",
                "total_pages": 10,
                "uploaded_at": "2024-01-01T00:00:00Z"
            }
        ],
        "total": 1
    }
    ```
    """
    document_service = DocumentService(current_user.user_id)
    documents, total = await document_service.list_documents(skip, limit)
    
    return DocumentListResponse(
        documents=documents,
        total=total
    )


@router.get("/{document_id}", response_model=Document)
async def get_document(
    document_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific document by ID.
    
    **Frontend Endpoint**: `GET /api/v1/documents/{document_id}`
    
    **Response**:
    ```json
    {
        "document_id": "uuid",
        "name": "document.pdf",
        "status": "ready",
        "total_pages": 10,
        "total_chunks": 45,
        "uploaded_at": "2024-01-01T00:00:00Z"
    }
    ```
    """
    document_service = DocumentService(current_user.user_id)
    document = await document_service.get_document(document_id)
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    return document


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Delete a document and all its associated data.
    
    **Frontend Endpoint**: `DELETE /api/v1/documents/{document_id}`
    
    **Response**: 204 No Content
    """
    document_service = DocumentService(current_user.user_id)
    success = await document_service.delete_document(document_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )


@router.get("/{document_id}/download-url")
async def get_document_download_url(
    document_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get a signed URL for downloading/viewing the PDF document.
    
    **Frontend Endpoint**: `GET /api/v1/documents/{document_id}/download-url`
    
    **Response**:
    ```json
    {
        "url": "https://signed-url-to-pdf",
        "expires_in": 3600
    }
    ```
    
    **Note**: Use this URL in frontend PDF viewer. URL is valid for 1 hour.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"Getting download URL for document {document_id}")
        document_service = DocumentService(current_user.user_id)
        document = await document_service.get_document(document_id)
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        url = await document_service.get_signed_url(document_id)
        
        return {
            "url": url,
            "expires_in": 3600
        }
    except ValueError as e:
        # Handle timeout or other value errors from get_signed_url
        logger.error(f"Error getting signed URL: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error getting download URL: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting download URL: {str(e)}"
        )


@router.get("/{document_id}/download")
async def download_document(
    document_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Download/stream the actual document file from local storage.
    """
    import os
    from fastapi.responses import FileResponse
    from config import settings
    
    document_service = DocumentService(current_user.user_id)
    document = await document_service.get_document(document_id)
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
        
    full_path = os.path.join(settings.LOCAL_STORAGE_PATH, document.storage_path)
    if not os.path.exists(full_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document file not found on disk"
        )
        
    return FileResponse(
        path=full_path,
        media_type="application/pdf" if document.name.lower().endswith(".pdf") else "application/octet-stream",
        filename=document.name
    )





