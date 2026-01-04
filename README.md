# Palmetto

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![C++](https://img.shields.io/badge/C%2B%2B-17-blue.svg)](https://isocpp.org/)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![OpenCASCADE](https://img.shields.io/badge/OpenCASCADE-7.8+-green.svg)](https://www.opencascade.com/)

A CAD Feature Recognition Tool with Graph-Based Analysis

## Overview

Palmetto is an expandable DFM (Design for Manufacturing) and feature checking tool that uses graph-based feature recognition to analyze CAD models. Built with FastAPI backend and React/Three.js frontend, it provides both computational and natural language interfaces for identifying manufacturing features.

## Key Features

- **Graph-Based Recognition**: Uses Attributed Adjacency Graph (AAG) following the Analysis Situs framework
- **Extensible Architecture**: Plugin-based recognizers for easy expansion
- **STEP File Support**: Import and analyze STEP CAD models (.step, .stp)
- **Natural Language Interface**: Powered by Claude API for intuitive feature queries
- **3D Visualization**: glTF-based rendering with face-level highlighting
- **DFM Analysis**: Comprehensive manufacturability checks for 5 manufacturing processes
- **Feature Detection**: Holes, cavities, pockets, fillets, chamfers, and more
- **Thickness Analysis**: Volumetric wall thickness calculation with visualization

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
├── core/              # C++ feature recognition engine
│   ├── apps/palmetto_engine/  # Main engine source
│   └── third_party/   # Dependencies (Analysis Situs, OpenCASCADE)
├── backend/           # FastAPI backend
│   └── app/
│       ├── api/       # REST endpoints
│       ├── core/      # C++ engine integration
│       ├── query/     # Natural language query engine
│       └── nl_processing/  # Claude API client
├── frontend/          # React frontend
│   └── src/
│       ├── components/  # UI components
│       ├── api/       # API client
│       └── types/     # TypeScript types
├── docs/              # Documentation
└── examples/          # Sample CAD models
```

## Quick Start

### 1. Build C++ Engine

```bash
cd core
mkdir -p .build && cd .build
cmake .. -DCMAKE_PREFIX_PATH=/path/to/opencascade
cmake --build . --config Release
# Binary will be at: .build/bin/palmetto_engine
```

See [core/docs/build-macos.md](core/docs/build-macos.md) for platform-specific build instructions.

### 2. Backend Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY (optional, for NL queries)

# Run server (ensure C++ engine is built first)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Visit http://localhost:5173 to use the application.

## Feature Recognizers

Implemented in C++ using Analysis Situs algorithms:
- **Holes**: Simple through-holes, countersunk, counterbored
- **Cavities & Pockets**: Recesses with depth classification (through-hole, blind pocket, shallow recess, deep cavity)
- **Fillets**: Toroidal blend surfaces with radius detection
- **Chamfers**: Beveled edges
- **Blends**: General blending features with constant radius

All recognizers operate on the Attributed Adjacency Graph (AAG) representation of the CAD model.

## DFM (Design for Manufacturing) Analysis

Comprehensive manufacturability checking for 5 processes:
- **Injection Molding**: Wall thickness, draft angles, undercuts, side action requirements
- **CNC Machining**: Tool accessibility, deep pockets, narrow openings, sharp corners
- **3D Printing (Additive)**: Overhang angles, support requirements
- **Sheet Metal**: Bend radii, hole proximity
- **Investment Casting**: Minimum walls, internal radii

DFM checks use advanced geometric analysis:
- **Ray-based undercut detection** - Volumetric obstruction analysis using Intel Embree
- **Pocket depth classification** - Aspect ratios and accessibility scoring
- **Thickness analysis** - Volumetric wall thickness with SDF (Signed Distance Field)

## API Endpoints

- `POST /api/analyze/upload` - Upload STEP file
- `POST /api/analyze/process` - Process model with C++ engine
- `GET /api/analyze/{model_id}/artifacts/{file}` - Download generated artifacts
- `POST /api/query/execute` - Execute natural language geometric query
- `GET /api/query/examples` - Get example queries
- `GET /api/graph/{model_id}` - Get AAG graph for visualization
- `GET /api/aag/{model_id}/graph` - Get full AAG data

See [API Documentation](docs/api-reference.md) for details.

## Technology Stack

**C++ Engine:**
- OpenCASCADE 7.8+ - CAD kernel
- Analysis Situs - Feature recognition framework
- RapidJSON - JSON output
- TinyGLTF - Mesh export

**Backend:**
- FastAPI - Web framework
- Anthropic SDK - Claude API for NL queries

**Frontend:**
- React - UI framework
- Three.js - 3D rendering
- TypeScript - Type safety
- Vite - Build tool
- PrimeReact - UI components

## Development

### Code Quality

```bash
# C++ (if you have clang-format)
cd core
find apps -name "*.cpp" -o -name "*.h" | xargs clang-format -i

# Backend
cd backend
black .
ruff check .

# Frontend
cd frontend
npm run lint
npm run format
```

## Deployment

Deploy Palmetto to production:

- **Quick Start**: See [DEPLOY_QUICKSTART.md](./DEPLOY_QUICKSTART.md) for 10-minute deployment
- **Full Guide**: See [DEPLOYMENT.md](./DEPLOYMENT.md) for detailed instructions

**Hosting:**
- Frontend: Vercel (free tier)
- Backend: Railway (free tier: $5/month credit)

## Documentation

- [Architecture Overview](docs/architecture.md)
- [Adding Recognizers](docs/recognizers.md)
- [AAG Specification](docs/aag-specification.md)
- [API Reference](docs/api-reference.md)
- [Deployment Guide](DEPLOYMENT.md)

## Roadmap

### Completed ✅
- [x] Graph-based feature recognition (AAG)
- [x] DFM rule checking for 5 manufacturing processes
- [x] Thickness analysis with volumetric SDF
- [x] Natural language query interface
- [x] Basic recognizers (holes, cavities, fillets, chamfers)

### In Progress / Planned
- [ ] Additional recognizers (threads, bosses, ribs, slots)
- [ ] AI/ML-based feature recognition enhancements
- [ ] Manufacturing cost estimation based on DFM violations
- [ ] Export to manufacturing formats (G-code, toolpaths)
- [ ] Multi-user collaboration and project management
- [ ] Database persistence for design history
- [ ] Support for additional file formats (IGES, Parasolid)
- [ ] Assembly analysis and BOM generation

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please read our [Contributing Guidelines](CONTRIBUTING.md) before submitting pull requests.

**Ways to contribute:**
- Report bugs and suggest features via GitHub Issues
- Improve documentation
- Add new feature recognizers
- Enhance DFM rules for different manufacturing processes
- Fix bugs and improve performance

## Acknowledgments

Based on the graph-based feature recognition framework from [Analysis Situs](https://analysissitus.org/features/features_feature-recognition-framework.html).
