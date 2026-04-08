"""
User model.
"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class User(BaseModel):
    """User model."""
    user_id: str
    email: Optional[str] = None
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True




