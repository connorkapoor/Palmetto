# Palmetto

A CAD Feature Recognition Tool with Graph-Based Analysis

## Overview

Palmetto is an expandable DFM (Design for Manufacturing) and feature checking tool that uses graph-based feature recognition to analyze CAD models. Built with FastAPI backend and React/Three.js frontend, it provides both computational and natural language interfaces for identifying manufacturing features.

## Key Features

- **Graph-Based Recognition**: Uses Attributed Adjacency Graph (AAG) following the Analysis Situs framework
- **Extensible Architecture**: Plugin-based recognizers for easy expansion
- **Multiple File Formats**: Support for STEP, IGES, and BREP files
- **Natural Language Interface**: Powered by Claude API for intuitive feature queries
- **3D Visualization**: glTF-based rendering with face-level highlighting
- **Feature Detection**: Holes, shafts, cavities, fillets, and more

## Architecture

### Backend (FastAPI + pythonOCC)
- **AAG Builder**: Constructs topology graph from B-Rep geometry
- **Feature Recognizers**: Modular plugins for different feature types
- **Geometric Analysis**: Dihedral angles, vertex convexity, surface classification
- **Meshing Pipeline**: Converts B-Rep to glTF with face metadata

### Frontend (React + Three.js)
- **File Upload**: Drag-and-drop CAD file upload
- **3D Viewer**: Interactive visualization with OrbitControls
- **Face Highlighting**: Click features to highlight corresponding faces
- **Natural Language Input**: Type commands like "find all holes larger than 10mm"

## Project Structure

```
palmetto/
├── backend/           # FastAPI backend
│   ├── app/
│   │   ├── core/      # CAD processing, AAG, meshing
│   │   ├── recognizers/  # Feature detection plugins
│   │   ├── api/       # REST endpoints
│   │   └── nl_processing/  # NL interface
│   └── tests/
├── frontend/          # React frontend
│   └── src/
│       ├── components/  # UI components
│       ├── api/       # API client
│       └── types/     # TypeScript types
├── docs/              # Documentation
└── examples/          # Sample CAD models
```

## Quick Start

### Backend Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY

# Run server
uvicorn app.main:app --reload
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Visit http://localhost:5173 to use the application.

## Feature Recognizers

Current recognizers (more coming):
- **Hole Detector**: Simple, countersunk, counterbored, and threaded holes
- **Shaft Detector**: Protruding cylindrical features
- **Cavity Detector**: Blind pockets and through cavities
- **Fillet Detector**: Rounded blend features
- **Sheet Metal Features**: Bends, flanges, etc.
- **CNC Milling Features**: Pockets, slots, etc.

## Adding New Recognizers

Create a new recognizer in `backend/app/recognizers/features/`:

```python
from app.recognizers.base import BaseRecognizer, RecognizedFeature
from app.recognizers.registry import register_recognizer

@register_recognizer
class MyFeatureRecognizer(BaseRecognizer):
    def get_name(self) -> str:
        return "my_feature_detector"

    def recognize(self, **kwargs) -> List[RecognizedFeature]:
        # Implement recognition logic using self.graph
        pass
```

That's it! The recognizer is automatically registered and available via API and NL interface.

## API Endpoints

- `POST /api/upload` - Upload CAD file
- `POST /api/recognition/recognize` - Run specific recognizer
- `POST /api/nl/parse` - Parse natural language command
- `POST /api/export/gltf` - Export to glTF
- `GET /api/recognition/recognizers` - List available recognizers

See [API Documentation](docs/api-reference.md) for details.

## Technology Stack

**Backend:**
- FastAPI - Web framework
- pythonOCC - OpenCASCADE bindings
- NumPy - Numerical computing
- pygltflib - glTF export
- Anthropic SDK - Claude API

**Frontend:**
- React - UI framework
- Three.js - 3D rendering
- TypeScript - Type safety
- Vite - Build tool

## Development

### Run Tests

```bash
cd backend
pytest

cd ../frontend
npm test
```

### Code Quality

```bash
# Backend
black .
ruff check .
mypy app

# Frontend
npm run lint
npm run format
```

## Documentation

- [Architecture Overview](docs/architecture.md)
- [Adding Recognizers](docs/recognizers.md)
- [AAG Specification](docs/aag-specification.md)
- [API Reference](docs/api-reference.md)

## Roadmap

- [ ] Additional recognizers (threads, chamfers, ribs)
- [ ] AI/ML-based feature recognition
- [ ] DFM rule checking
- [ ] Manufacturing cost estimation
- [ ] Export to manufacturing formats (G-code, toolpaths)
- [ ] Multi-user collaboration
- [ ] Database persistence

## License

MIT

## Contributing

Contributions welcome! Please read our contributing guidelines and submit pull requests.

## Acknowledgments

Based on the graph-based feature recognition framework from [Analysis Situs](https://analysissitus.org/features/features_feature-recognition-framework.html).
