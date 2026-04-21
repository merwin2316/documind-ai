"""
Local SQLite database for demo/development mode.
Used when Supabase is not configured.
"""
import sqlite3
import json
import os
import logging
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

_db_path: str = "./documind.db"
_initialized: bool = False


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_local_db(db_path: str = "./documind.db"):
    """Initialize SQLite tables if they don't exist."""
    global _db_path, _initialized
    _db_path = db_path

    if _initialized:
        return

    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            email TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS documents (
            document_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            storage_path TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            file_type TEXT DEFAULT 'application/pdf',
            status TEXT DEFAULT 'processing',
            total_pages INTEGER,
            total_chunks INTEGER,
            category TEXT,
            tags TEXT,
            ai_summary TEXT,
            key_entities TEXT,
            related_document_ids TEXT,
            uploaded_at TEXT DEFAULT (datetime('now')),
            processed_at TEXT,
            error_message TEXT
        );

        CREATE TABLE IF NOT EXISTS conversations (
            conversation_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            title TEXT,
            is_pinned INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS messages (
            message_id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL,
            user_message TEXT NOT NULL,
            assistant_message TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (conversation_id) REFERENCES conversations(conversation_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS citations (
            citation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id TEXT NOT NULL,
            document_id TEXT NOT NULL,
            chunk_id TEXT NOT NULL,
            page INTEGER NOT NULL,
            start_char INTEGER NOT NULL,
            end_char INTEGER NOT NULL,
            text_snippet TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS document_chunks (
            chunk_id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            page INTEGER NOT NULL,
            start_char INTEGER NOT NULL,
            end_char INTEGER NOT NULL,
            text TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    conn.close()

    _initialized = True
    logger.info(f"Local SQLite database initialized at {_db_path}")


class LocalDB:
    """Simple wrapper that mimics Supabase's table().select().eq() chain for SQLite."""

    def __init__(self):
        init_local_db()

    # ---- Users ----
    def get_user(self, user_id: str) -> Optional[Dict]:
        conn = _get_conn()
        row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def upsert_user(self, user_id: str, email: str = None):
        conn = _get_conn()
        conn.execute(
            "INSERT OR IGNORE INTO users (user_id, email) VALUES (?, ?)",
            (user_id, email),
        )
        conn.commit()
        conn.close()

    # ---- Documents ----
    def insert_document(self, data: Dict):
        conn = _get_conn()
        # Serialize JSON fields
        data = dict(data)
        for key in ("tags", "key_entities", "related_document_ids"):
            if key in data and not isinstance(data.get(key), str):
                data[key] = json.dumps(data[key]) if data[key] else None

        cols = ", ".join(data.keys())
        placeholders = ", ".join("?" for _ in data)
        conn.execute(f"INSERT INTO documents ({cols}) VALUES ({placeholders})", list(data.values()))
        conn.commit()
        conn.close()

    def get_document(self, document_id: str, user_id: str) -> Optional[Dict]:
        conn = _get_conn()
        row = conn.execute(
            "SELECT * FROM documents WHERE document_id = ? AND user_id = ?",
            (document_id, user_id),
        ).fetchone()
        conn.close()
        if not row:
            return None
        d = dict(row)
        # Deserialize JSON fields
        for key in ("tags", "key_entities", "related_document_ids"):
            if d.get(key) and isinstance(d[key], str):
                try:
                    d[key] = json.loads(d[key])
                except json.JSONDecodeError:
                    pass
        return d

    def list_documents(self, user_id: str, skip: int = 0, limit: int = 20) -> tuple:
        conn = _get_conn()
        total = conn.execute(
            "SELECT COUNT(*) FROM documents WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
        rows = conn.execute(
            "SELECT * FROM documents WHERE user_id = ? ORDER BY uploaded_at DESC LIMIT ? OFFSET ?",
            (user_id, limit, skip),
        ).fetchall()
        conn.close()
        docs = []
        for row in rows:
            d = dict(row)
            for key in ("tags", "key_entities", "related_document_ids"):
                if d.get(key) and isinstance(d[key], str):
                    try:
                        d[key] = json.loads(d[key])
                    except json.JSONDecodeError:
                        pass
            docs.append(d)
        return docs, total

    def update_document(self, document_id: str, data: Dict):
        conn = _get_conn()
        data = dict(data)
        for key in ("tags", "key_entities", "related_document_ids"):
            if key in data and not isinstance(data.get(key), str):
                data[key] = json.dumps(data[key]) if data[key] else None
        sets = ", ".join(f"{k} = ?" for k in data.keys())
        conn.execute(f"UPDATE documents SET {sets} WHERE document_id = ?", list(data.values()) + [document_id])
        conn.commit()
        conn.close()

    def delete_document(self, document_id: str, user_id: str):
        conn = _get_conn()
        conn.execute("DELETE FROM document_chunks WHERE document_id = ?", (document_id,))
        conn.execute("DELETE FROM documents WHERE document_id = ? AND user_id = ?", (document_id, user_id))
        conn.commit()
        conn.close()

    # ---- Conversations ----
    def insert_conversation(self, data: Dict):
        conn = _get_conn()
        cols = ", ".join(data.keys())
        placeholders = ", ".join("?" for _ in data)
        conn.execute(f"INSERT INTO conversations ({cols}) VALUES ({placeholders})", list(data.values()))
        conn.commit()
        conn.close()

    def get_conversation(self, conversation_id: str, user_id: str) -> Optional[Dict]:
        conn = _get_conn()
        row = conn.execute(
            "SELECT * FROM conversations WHERE conversation_id = ? AND user_id = ?",
            (conversation_id, user_id),
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def list_conversations(self, user_id: str, skip: int = 0, limit: int = 50) -> tuple:
        conn = _get_conn()
        total = conn.execute(
            "SELECT COUNT(*) FROM conversations WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
        rows = conn.execute(
            "SELECT * FROM conversations WHERE user_id = ? ORDER BY updated_at DESC LIMIT ? OFFSET ?",
            (user_id, limit, skip),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows], total

    def update_conversation(self, conversation_id: str, user_id: str, data: Dict):
        conn = _get_conn()
        data["updated_at"] = datetime.utcnow().isoformat()
        sets = ", ".join(f"{k} = ?" for k in data.keys())
        conn.execute(
            f"UPDATE conversations SET {sets} WHERE conversation_id = ? AND user_id = ?",
            list(data.values()) + [conversation_id, user_id],
        )
        conn.commit()
        conn.close()

    def delete_conversation(self, conversation_id: str, user_id: str):
        conn = _get_conn()
        # Delete messages first (cascade)
        conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
        conn.execute(
            "DELETE FROM conversations WHERE conversation_id = ? AND user_id = ?",
            (conversation_id, user_id),
        )
        conn.commit()
        conn.close()

    # ---- Messages ----
    def insert_message(self, data: Dict):
        conn = _get_conn()
        cols = ", ".join(data.keys())
        placeholders = ", ".join("?" for _ in data)
        conn.execute(f"INSERT INTO messages ({cols}) VALUES ({placeholders})", list(data.values()))
        conn.commit()
        conn.close()

    def get_messages(self, conversation_id: str) -> List[Dict]:
        conn = _get_conn()
        rows = conn.execute(
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC",
            (conversation_id,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ---- Citations ----
    def insert_citation(self, data: Dict):
        conn = _get_conn()
        cols = ", ".join(data.keys())
        placeholders = ", ".join("?" for _ in data)
        conn.execute(f"INSERT INTO citations ({cols}) VALUES ({placeholders})", list(data.values()))
        conn.commit()
        conn.close()

    def get_citations(self, message_id: str) -> List[Dict]:
        conn = _get_conn()
        rows = conn.execute(
            "SELECT * FROM citations WHERE message_id = ?", (message_id,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ---- Document Chunks ----
    def insert_chunks(self, chunks: List[Dict]):
        if not chunks:
            return
        conn = _get_conn()
        for chunk in chunks:
            cols = ", ".join(chunk.keys())
            placeholders = ", ".join("?" for _ in chunk)
            conn.execute(f"INSERT OR REPLACE INTO document_chunks ({cols}) VALUES ({placeholders})", list(chunk.values()))
        conn.commit()
        conn.close()

    def get_chunks(self, document_id: str) -> List[Dict]:
        conn = _get_conn()
        rows = conn.execute(
            "SELECT * FROM document_chunks WHERE document_id = ?", (document_id,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ---- Knowledge Base helpers ----
    def get_categories(self, user_id: str) -> List[Dict]:
        conn = _get_conn()
        rows = conn.execute(
            "SELECT category as name, COUNT(*) as count FROM documents WHERE user_id = ? AND category IS NOT NULL GROUP BY category",
            (user_id,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_tags(self, user_id: str) -> List[Dict]:
        conn = _get_conn()
        rows = conn.execute(
            "SELECT tags FROM documents WHERE user_id = ? AND tags IS NOT NULL",
            (user_id,),
        ).fetchall()
        conn.close()
        tag_counts: Dict[str, int] = {}
        for row in rows:
            try:
                tags = json.loads(row["tags"]) if isinstance(row["tags"], str) else row["tags"]
                for tag in (tags or []):
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1
            except (json.JSONDecodeError, TypeError):
                pass
        return [{"name": t, "count": c} for t, c in sorted(tag_counts.items(), key=lambda x: -x[1])]
