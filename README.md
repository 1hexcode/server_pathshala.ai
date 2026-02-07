# PathshalaAI — Server

> FastAPI backend for PDF text extraction and AI-powered summarization.

## Quick Start

### 1. Start PostgreSQL (Docker)

```bash
docker compose up -d
```

### 2. Set up Python environment

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure environment

Copy `.env.sample` to `.env` and fill in your keys:

```env
DEBUG=true
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/patshala
GROQ_API_KEY=gsk_your-key-here
OPENROUTER_API_KEY=sk-or-v1-your-key-here
```

### 4. Run database migrations

```bash
alembic revision --autogenerate -m "initial tables"
alembic upgrade head
```

### 5. Start the server

```bash
uvicorn app.main:app --reload
```

API docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Health check / API info |
| GET | `/health` | Health status |
| POST | `/api/v1/pdf/summarize` | Upload PDF → AI summary |

**Query params** for `/summarize`:
- `platform` — `groq` (default) or `openrouter`

## Project Structure

```
server/
├── app/
│   ├── main.py                       # FastAPI entry point
│   ├── api/v1/
│   │   ├── router.py                 # API v1 router
│   │   └── endpoints/pdf.py          # PDF summarize endpoint
│   ├── core/
│   │   ├── config.py                 # Settings (env vars)
│   │   ├── database.py               # Async SQLAlchemy engine
│   │   └── logging.py                # Logger setup
│   ├── models/                       # SQLAlchemy models
│   │   ├── user.py, college.py
│   │   ├── program.py, subject.py
│   │   ├── note.py, summary.py
│   │   └── __init__.py
│   └── services/
│       ├── pdf_service.py            # PDF text extraction & cleaning
│       └── summarization_service.py  # LLM summarization (Groq/OpenRouter)
├── migrations/                       # Alembic migrations
├── docker-compose.yml                # PostgreSQL 16
├── requirements.txt
└── .env
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DEBUG` | `false` | Enable debug logging |
| `DATABASE_URL` | `postgresql+asyncpg://...` | PostgreSQL connection |
| `GROQ_API_KEY` | — | Groq API key |
| `GROQ_MODEL` | `llama-3.1-8b-instant` | Groq model |
| `OPENROUTER_API_KEY` | — | OpenRouter API key |
| `OPENROUTER_MODEL` | `meta-llama/llama-3.1-70b-versatile` | OpenRouter model |
| `DEFAULT_LLM_PLATFORM` | `groq` | Default LLM platform |

## Database

**Models**: User, College, Program, Subject, Note, Summary

```bash
# Access PostgreSQL shell
docker exec -it patshala_db psql -U postgres -d patshala

# List all tables
\dt

# Exit
\q
```

```bash
# Create a new migration after model changes
alembic revision --autogenerate -m "describe change"

# Apply migrations
alembic upgrade head

# Rollback one step
alembic downgrade -1
```

## Testing

```bash
pytest tests/ -v
```
