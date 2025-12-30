# Palmetto Backend

FastAPI backend for Palmetto CAD feature recognition tool.

## Features

- C++ engine integration for feature recognition
- Natural language geometric queries via Claude API
- AAG graph serving and visualization
- REST API for frontend

## Prerequisites

- Python 3.9+
- C++ engine built (see `core/` directory)
- Anthropic API key (optional, for NL queries)

## Installation

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY if using NL queries
```

## Running the Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The C++ engine binary will be automatically located at:
1. `$PALMETTO_ENGINE_PATH` (if set)
2. `../core/.build/bin/palmetto_engine` (default)

## API Documentation

Once running, visit:
- Swagger UI: http://localhost:8000/docs
- Health check: http://localhost:8000/health

## Project Structure

```
app/
├── main.py              # FastAPI application entry point
├── config.py            # Configuration management
├── api/                 # API routes
│   └── routes/
│       ├── analyze.py   # C++ engine integration
│       ├── query.py     # NL query execution
│       ├── aag.py       # AAG data serving
│       └── graph.py     # Graph visualization
├── core/
│   └── cpp_engine.py    # C++ engine wrapper
├── query/               # Query engine and parser
├── nl_processing/       # Claude API client
└── storage/             # Model storage
```

## Environment Variables

Create a `.env` file:

```env
# Claude API (optional, for natural language queries)
ANTHROPIC_API_KEY=your_api_key_here

# Server settings
CORS_ORIGINS=http://localhost:5173
HOST=0.0.0.0
PORT=8000

# Optional: Override C++ engine path
# PALMETTO_ENGINE_PATH=/path/to/palmetto_engine
```
