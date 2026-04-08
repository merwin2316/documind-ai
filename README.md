# DocuMind AI 🧠

**An intelligent document analysis system powered by RAG (Retrieval-Augmented Generation).**

DocuMind AI ingests, processes, and retrieves knowledge from PDF and DOCX documents. It features a multi-agent RAG pipeline, an AI-organized Knowledge Base, and a full-featured Chat interface with real-time streaming.

---

## ✨ Features

### 🔍 Intelligent RAG System
- **Multi-Agent Architecture** — Specialized agents (Intent, Answer, Transform) for high-precision answers
- **Token-Based Chunking** — Semantic sentence splitting (800 tokens/chunk) for optimal context
- **Inline Citations** — Every answer cites exact pages and passages

### 📚 Smart Knowledge Base
- **Auto-Categorization** — AI sorts documents into categories (Legal, Financial, HR, etc.)
- **Smart Tagging** — Extracts key topics/tags for powerful filtering
- **Related Documents** — Finds semantically similar documents via vector similarity
- **Processing Pipeline** — Track status, page counts, and chunk statistics

### 💬 Chat Interface
- **Conversation Memory** — Contextual follow-up questions with pronoun resolution
- **Streaming Responses** — Real-time token streaming via SSE
- **Chat Management** — Pin, rename, and delete conversations

---

## 🏗️ Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Frontend   │────▶│  FastAPI API  │────▶│   OpenAI     │
│  (Next.js)   │     │  (Python)    │     │  (GPT-4o)    │
└──────────────┘     └──────┬───────┘     └──────────────┘
                            │
                    ┌───────┼───────┐
                    ▼       ▼       ▼
              ┌─────────┐ ┌─────┐ ┌──────────┐
              │ Supabase│ │Qdrant│ │ Supabase │
              │  (PgSQL)│ │(Vec) │ │ Storage  │
              └─────────┘ └─────┘ └──────────┘
```

| Layer       | Technology                           |
| :---------- | :----------------------------------- |
| Backend     | Python 3.11+, FastAPI                |
| Frontend    | Next.js 15, TypeScript, Tailwind CSS |
| Database    | Supabase (PostgreSQL + Auth)         |
| Vector DB   | Qdrant                               |
| AI Engine   | OpenAI GPT-4o + text-embedding-3-large |
| File Storage| Supabase Storage                     |

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- Docker (for Qdrant)

### 1. Backend Setup
```bash
# Clone & enter
git clone https://github.com/your-username/DocuMindAI.git
cd DocuMindAI

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys (Supabase, OpenAI, Qdrant)

# Start Qdrant (Vector DB)
docker run -d -p 6333:6333 qdrant/qdrant

# Start API Server
python run.py
# → http://localhost:8000
# → Docs: http://localhost:8000/docs
```

### 2. Database Setup
Run the SQL schema in your Supabase SQL editor:
```bash
# File: app/database/schema.sql
```

### 3. Frontend Setup
```bash
cd frontend

# Install dependencies
npm install

# Configure environment
cp .env.example .env.local
# Add NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY

# Start dev server
npm run dev
# → http://localhost:3000
```

---

## 📡 API Reference

### Documents
| Method   | Endpoint                              | Description                    |
| :------- | :------------------------------------ | :----------------------------- |
| `POST`   | `/api/v1/documents/upload`            | Upload PDF/DOCX for processing |
| `GET`    | `/api/v1/documents/`                  | List user's documents          |
| `GET`    | `/api/v1/documents/{id}`              | Get document details           |
| `DELETE` | `/api/v1/documents/{id}`              | Delete document + chunks       |
| `GET`    | `/api/v1/documents/{id}/download-url` | Signed download URL            |

### Chat
| Method   | Endpoint                              | Description                    |
| :------- | :------------------------------------ | :----------------------------- |
| `POST`   | `/api/v1/chat/message`                | Send message, get RAG response |
| `POST`   | `/api/v1/chat/stream`                 | Stream response via SSE        |
| `GET`    | `/api/v1/chat/conversations`          | List conversations             |
| `GET`    | `/api/v1/chat/conversations/{id}`     | Get conversation + messages    |
| `PUT`    | `/api/v1/chat/conversations/{id}`     | Update title / pin status      |
| `DELETE` | `/api/v1/chat/conversations/{id}`     | Delete conversation            |

### Knowledge Base
| Method   | Endpoint                                       | Description              |
| :------- | :--------------------------------------------- | :----------------------- |
| `GET`    | `/api/v1/knowledge-base/categories`            | Categories + counts      |
| `GET`    | `/api/v1/knowledge-base/documents`             | Filter by category/tags  |
| `GET`    | `/api/v1/knowledge-base/tags`                  | All tags + frequency     |
| `GET`    | `/api/v1/knowledge-base/documents/{id}/related`| Related documents        |

---

## 📁 Project Structure

```
DocuMindAI/
├── app/
│   ├── agents/              # AI agents (intent, answer, transform, categorization)
│   ├── api/v1/              # FastAPI route handlers
│   ├── database/            # Supabase client + SQL schema
│   ├── middleware/          # JWT auth middleware
│   ├── models/              # Pydantic data models
│   ├── services/            # Core business logic
│   │   ├── rag_service.py       # RAG orchestrator
│   │   ├── vector_store.py      # Qdrant operations
│   │   ├── document_processor.py# PDF/DOCX chunking
│   │   ├── document_service.py  # Document CRUD
│   │   └── websocket_manager.py # Real-time updates
│   └── main.py              # FastAPI app entry point
├── frontend/                # Next.js frontend
├── tests/                   # Regression tests
├── config.py                # Settings from .env
├── run.py                   # Dev server runner
├── requirements.txt         # Python dependencies
├── Dockerfile               # Backend container
└── .env.example             # Environment template
```

---

## ⚙️ Configuration

Core RAG parameters (set via environment or `config.py` defaults):

| Variable           | Default | Description                    |
| :----------------- | :------ | :----------------------------- |
| `CHUNK_SIZE`       | 800     | Tokens per chunk               |
| `CHUNK_OVERLAP`    | 150     | Overlap tokens for context     |
| `TOP_K_RETRIEVAL`  | 15      | Chunks to retrieve per query   |
| `CHUNK_METHOD`     | token   | `token` or `character`         |
| `SEMANTIC_SPLITTING` | True  | Split at sentence boundaries   |

---

## 🧪 Testing

```bash
pytest tests/ -v
```

---

## 🐳 Docker

```bash
# Build backend
docker build -t documind-ai .

# Run with env file
docker run --env-file .env -p 8000:8080 documind-ai
```

---

## 📄 License

MIT License
