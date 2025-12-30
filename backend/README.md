# Palmetto Backend

CAD Feature Recognition Tool - FastAPI Backend

## Features

- Graph-based feature recognition using Attributed Adjacency Graph (AAG)
- Support for STEP, IGES, and BREP file formats
- Extensible plugin architecture for feature recognizers
- Natural language interface via Claude API
- glTF export with face-level metadata for visualization

## Installation

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Running the Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## API Documentation

Once running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Project Structure

```
app/
├── main.py                 # FastAPI application entry point
├── config.py               # Configuration management
├── api/                    # API routes and schemas
├── core/                   # Core CAD processing
│   ├── cad_loader.py      # STEP/IGES/BREP loader
│   ├── topology/          # AAG implementation
│   ├── geometry/          # Geometric analysis
│   └── meshing/           # Tessellation and glTF export
├── recognizers/           # Feature recognizers
│   ├── base.py           # Base recognizer class
│   ├── registry.py       # Plugin registry
│   ├── features/         # Feature recognizers (holes, fillets, etc.)
│   └── analysis/         # Analysis tools
├── nl_processing/        # Natural language interface
└── storage/              # In-memory model storage
```

## Development

```bash
# Run tests
pytest

# Format code
black .

# Lint code
ruff check .

# Type check
mypy app
```

## Environment Variables

Create a `.env` file:

```env
# Claude API
ANTHROPIC_API_KEY=your_api_key_here

# Server settings
CORS_ORIGINS=http://localhost:5173
MAX_UPLOAD_SIZE=104857600  # 100MB

# Tessellation
LINEAR_DEFLECTION=0.1
ANGULAR_DEFLECTION=0.5
```
