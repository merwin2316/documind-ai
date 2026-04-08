"""
Supabase client singleton.
"""
from supabase import create_client, Client
from config import settings
from typing import Optional

_supabase_client: Optional[Client] = None


async def get_supabase_client() -> Client:
    """
    Get or create Supabase client instance.
    
    Returns:
        Supabase client
    """
    global _supabase_client
    
    if _supabase_client is None:
        _supabase_client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_KEY  # Use service key for backend operations
        )
    
    return _supabase_client




