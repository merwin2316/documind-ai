# DocuMind AI 🧠

> **A RAG-based document intelligence system with modular LLM support (Ollama/Groq), designed for fully local and cost-efficient deployment.**

DocuMind AI ingests, processes, and retrieves knowledge from PDF and DOCX documents using **local LLMs via Ollama** — no paid API keys required. It features a multi-agent RAG pipeline, an AI-organized Knowledge Base, and a full-featured Chat interface with real-time streaming.

**No OpenAI. No paid APIs. Fully local. Recruiter-ready.**

---

## 💡 Key Features

- 🔍 **RAG-based document intelligence system** — upload and query PDF, DOCX files
- 🔗 **Hybrid search** — semantic vector search + metadata filtering
- 📝 **Citation-aware responses** — every answer cites exact pages and passages
- 🤖 **Modular LLM provider** — swap between Ollama (local) and Groq (cloud) with one env var
- 🏠 **Fully local deployment** — no cloud dependency, runs on your machine
- 📚 **Smart Knowledge Base** — AI auto-categorizes, tags, and links related documents
- 💬 **Streaming Chat** — real-time token streaming via SSE with conversation memory

---

## 🤖 LLM Support

DocuMind AI supports multiple LLM providers:

| Provider | Type | Models | Cost |
|:---------|:-----|:-------|:-----|
| **Ollama** (default) | Local | llama3, nomic-embed-text | **Free** |
| **Groq** (optional) | Cloud | llama-3.3-70b-versatile | **Free tier** |

> **No dependency on paid APIs like OpenAI.** The entire system runs on free, open-source models.

---

## 🏗️ Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Frontend   │────▶│  FastAPI API  │────▶│   LLM Layer  │
│  (Next.js)   │     │  (Python)    │     │ Ollama/Groq  │
└──────────────┘     └──────┬───────┘     └──────────────┘
                            │
                    ┌───────┼────────┐
                    ▼       ▼        ▼
              ┌─────────┐ ┌─────┐ ┌────────────┐
              │ SQLite  │ │Qdrant│ │ Local/Opt  │
              │ (Meta)  │ │(Vec) │ │ Storage    │
              └─────────┘ └─────┘ └────────────┘
```

| Layer        | Technology                                      |
| :----------- | :---------------------------------------------- |
| Backend      | Python 3.11+, FastAPI                            |
| Frontend     | Next.js 15, TypeScript, Tailwind CSS             |
| Database     | SQLite (default) / Supabase (optional)           |
| Vector DB    | Qdrant                                           |
| AI Engine    | Ollama (local, free) / Groq (free cloud API)     |
| Embeddings   | Ollama nomic-embed-text (768 dims)               |
| File Storage | Local filesystem / Supabase Storage (optional)   |

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- Docker (for Qdrant)
- [Ollama](https://ollama.com/download) (for local LLM)

---

### 1. Backend Setup

```bash
git clone https://github.com/merwin2316/documind-ai.git
cd documind-ai

python -m venv venv
venv\Scripts\activate   # Windows
# source venv/bin/activate  # Mac/Linux

pip install -r requirements.txt

cp .env.example .env
```

Edit `.env` (minimum required):
```env
MODEL_PROVIDER=ollama
OLLAMA_MODEL=llama3
DATABASE_URL=sqlite:///./documind.db
```

### 2. Start Services

```bash
# Start Qdrant (vector database)
docker run -d -p 6333:6333 qdrant/qdrant

# Pull and start Ollama models
ollama pull llama3
ollama pull nomic-embed-text

# Start backend
python run.py
```

- **API**: http://localhost:8000
- **Docs**: http://localhost:8000/docs

### 3. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

- **Frontend**: http://localhost:3000

---

## 🔧 LLM Configuration

### Option A: Ollama (Default — Local, Free)
```env
MODEL_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
```

### Option B: Groq (Cloud, Free Tier)
```env
MODEL_PROVIDER=groq
GROQ_API_KEY=gsk_your_key_here
GROQ_MODEL=llama-3.3-70b-versatile
# Note: Groq has no embedding API — Ollama is still needed for embeddings
```

### Troubleshooting

| Problem | Solution |
|:--------|:---------|
| "Cannot connect to Ollama" | Run `ollama serve` or check installation |
| "Model not found" | Run `ollama pull llama3` and `ollama pull nomic-embed-text` |
| Slow responses | Try a smaller model: `OLLAMA_MODEL=llama3:8b` |
| Want cloud speed | Switch to Groq: `MODEL_PROVIDER=groq` |

---

## 📡 API Reference

### Documents
| Method   | Endpoint                              | Description                    |
| :------- | :------------------------------------ | :----------------------------- |
| `POST`   | `/api/v1/documents/upload`            | Upload PDF/DOCX for processing |
| `GET`    | `/api/v1/documents/`                  | List user's documents          |
| `GET`    | `/api/v1/documents/{id}`              | Get document details           |
| `DELETE` | `/api/v1/documents/{id}`              | Delete document + chunks       |

### Chat
| Method   | Endpoint                              | Description                    |
| :------- | :------------------------------------ | :----------------------------- |
| `POST`   | `/api/v1/chat/message`                | Send message, get RAG response |
| `POST`   | `/api/v1/chat/stream`                 | Stream response via SSE        |
| `GET`    | `/api/v1/chat/conversations`          | List conversations             |
| `PUT`    | `/api/v1/chat/conversations/{id}`     | Update title / pin             |
| `DELETE` | `/api/v1/chat/conversations/{id}`     | Delete conversation            |

### Knowledge Base
| Method   | Endpoint                                       | Description              |
| :------- | :--------------------------------------------- | :----------------------- |
| `GET`    | `/api/v1/knowledge-base/categories`            | Categories + counts      |
| `GET`    | `/api/v1/knowledge-base/documents`             | Filter by category/tags  |
| `GET`    | `/api/v1/knowledge-base/tags`                  | All tags + frequency     |

---

## 📁 Project Structure

```
DocuMindAI/
├── app/
│   ├── agents/              # AI agents (intent, answer, transform, categorization)
│   ├── api/v1/              # FastAPI route handlers
│   ├── database/            # SQLite local DB + optional Supabase client
│   ├── middleware/          # Auth (dev bypass in local mode)
│   ├── models/              # Pydantic data models
│   ├── services/            # Core logic (RAG, vector store, documents)
│   └── main.py              # FastAPI entry point
├── shared/
│   └── llm/                 # LLM provider abstraction layer
│       ├── base.py              # Abstract interface
│       ├── ollama_provider.py   # Ollama (local, default)
│       ├── groq_provider.py     # Groq (cloud fallback)
│       └── factory.py           # Provider factory
├── frontend/                # Next.js frontend
├── config.py                # Settings (all optional w/ defaults)
├── requirements.txt         # Python deps (no OpenAI!)
└── .env.example             # Environment template
```

---

## 🐳 Docker (One Command)

```bash
docker-compose up
```

---

## ⚙️ Optional: Supabase Mode

For production auth and cloud storage, set these in `.env`:
```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-role-key
SUPABASE_JWT_SECRET=your-jwt-secret
```

When Supabase is not configured, the system automatically uses:
- **SQLite** for metadata storage
- **Local filesystem** for document files
- **Dev user bypass** for authentication

---

## 📄 License

MIT License
