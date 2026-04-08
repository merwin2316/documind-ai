"""
WebSocket Connection Manager.
Handles active WebSocket connections and broadcasting messages.
"""
from typing import Dict, List, Set, Optional
from fastapi import WebSocket
import logging
import json

logger = logging.getLogger(__name__)

class ConnectionManager:
    """
    Manages WebSocket connections for real-time updates.
    Sorts connections by user_id to ensure private updates.
    """
    
    def __init__(self):
        # user_id -> List of active WebSockets
        self.active_connections: Dict[str, List[WebSocket]] = {}
        
    async def register(self, websocket: WebSocket, user_id: str):
        """Register an already accepted connection."""
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        logger.info(f"WebSocket connected for user {user_id}. Total connections: {len(self.active_connections.get(user_id, []))}")
        
    def disconnect(self, websocket: WebSocket, user_id: str):
        """Remove connection."""
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
            
            # Clean up empty lists
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
                
        logger.info(f"WebSocket disconnected for user {user_id}")
        
    async def broadcast_to_user(self, user_id: str, message: dict):
        """Send a JSON message to all open connections for a specific user."""
        if user_id not in self.active_connections:
            return
            
        disconnected = []
        for connection in self.active_connections[user_id]:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"Error sending to websocket: {e}")
                disconnected.append(connection)
        
        # Cleanup broken connections
        for connection in disconnected:
            self.disconnect(connection, user_id)

# Global instance
manager = ConnectionManager()

def get_connection_manager() -> ConnectionManager:
    return manager
