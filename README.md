# Patshala.ai

A FastAPI-based API service for PDF text extraction and AI-powered summarization.

## Features

- **PDF Text Extraction**: Upload PDFs and extract cleaned text content
- **AI Summarization**: Get LLM-generated summaries of PDF documents via OpenRouter
- **Free Model Support**: Uses free models like `google/gemma-3-1b-it:free` by default

## Quick Start

```bash
cd server
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Set your OpenRouter API key in `.env`:
```env
DEBUG=true
OPENROUTER_API_KEY=sk-or-v1-your-key-here
```

Get a free key at [openrouter.ai/keys](https://openrouter.ai/keys).

Run the server:
```bash
uvicorn app.main:app --reload
```

API docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Root / API info |
| GET | `/health` | Health check |
| POST | `/api/v1/pdf/extract` | Extract and clean text from PDF |
| POST | `/api/v1/pdf/summarize` | Summarize a PDF via AI |

## Project Structure

```
server/
├── app/
│   ├── main.py                  # FastAPI entry point
│   ├── api/v1/
│   │   ├── router.py            # API v1 router
│   │   └── endpoints/pdf.py     # PDF endpoints (extract + summarize)
│   ├── core/
│   │   ├── config.py            # Settings (env vars)
│   │   └── logging.py           # Logger setup
│   └── services/
│       ├── pdf_service.py       # PDF text extraction & cleaning
│       └── summarization_service.py  # OpenRouter LLM summarization
├── tests/
├── requirements.txt
└── .env
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DEBUG` | `false` | Enable debug logging |
| `OPENROUTER_API_KEY` | — | Your OpenRouter API key (required for `/summarize`) |
| `OPENROUTER_MODEL` | `google/gemma-3-1b-it:free` | Model to use for summarization |

## Testing

```bash
pytest tests/ -v
```
