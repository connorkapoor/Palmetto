# Palmetto Architecture

Palmetto is a web-based CAD feature recognition system built on Analysis Situs and OpenCASCADE.

## System Overview

```
┌─────────────┐
│   Browser   │  ← React + Three.js viewer
└──────┬──────┘
       │ HTTP/JSON
       ▼
┌─────────────┐
│  FastAPI    │  ← Python API server
│  Backend    │
└──────┬──────┘
       │ subprocess call
       ▼
┌─────────────┐
│  C++ Engine │  ← palmetto_engine (headless)
│  Analysis   │     - OCCT for CAD kernel
│  Situs SDK  │     - Analysis Situs for recognition
└─────────────┘
```

## Components

### 1. C++ Engine (`core/apps/palmetto_engine`)

**Purpose**: Headless feature recognition engine using Analysis Situs

**Capabilities**:
- Load STEP files (ISO 10303-21)
- Build Attributed Adjacency Graph (AAG)
- Run feature recognizers:
  - Holes (simple, countersunk, counterbored)
  - Shafts (cylindrical protrusions)
  - Fillets (edge-based blends)
  - Cavities (pockets, slots)
- Generate 3D mesh (glTF format)
- Export triangle→face mapping for highlighting

**Command Line Interface**:
```bash
palmetto_engine \
  --input model.step \
  --outdir ./output \
  --modules all \
  --mesh-quality 0.35
```

**Outputs**:
- `mesh.glb` - 3D mesh in glTF binary format
- `tri_face_map.bin` - Triangle to face ID mapping (uint32 array)
- `features.json` - Recognized features with metadata
- `aag.json` - Attributed Adjacency Graph
- `meta.json` - Processing metadata (timings, counts, warnings)

### 2. FastAPI Backend (`backend/`)

**Purpose**: HTTP API wrapper around C++ engine

**Endpoints**:

```
POST /v1/models
  - Upload STEP file
  - Returns: {model_id}

POST /v1/models/{model_id}/analyze
  - Trigger feature recognition
  - Body: {modules: "all", mesh_quality: 0.35}
  - Returns: {job_id}

GET /v1/jobs/{job_id}
  - Check job status
  - Returns: {status: "queued"|"running"|"done"|"error", progress: 0-100}

GET /v1/models/{model_id}/artifacts
  - Download mesh.glb, features.json, etc.
  - Returns: {urls: {...}}
```

**Job Execution**:
- MVP: Synchronous subprocess call to `palmetto_engine`
- Production: Redis-backed job queue (RQ/Celery)

**Storage**:
- MVP: Local filesystem (`./data/{model_id}/`)
- Production: S3-compatible storage

### 3. Web Frontend (`frontend/`)

**Technology**: Next.js + React + Three.js

**Features**:
- Upload STEP files
- View 3D models
- Feature list (grouped by type)
- Click feature → highlight triangles
- Display feature properties (diameter, depth, etc.)

**Highlighting Implementation**:

```javascript
// Load triangle→face mapping
const mapping = await loadTriFaceMap(modelId);  // Uint32Array

// User clicks feature with faces [12, 77]
const featureFaces = new Set([12, 77]);

// Find all triangles belonging to those faces
const highlightedTriangles = [];
for (let i = 0; i < mapping.length; i++) {
  if (featureFaces.has(mapping[i])) {
    highlightedTriangles.push(i);
  }
}

// Update mesh colors
updateMeshColors(highlightedTriangles, 'orange');
```

## Critical Bridge: Triangle→Face Mapping

**The Problem**: Analysis Situs operates on B-rep faces, web viewer renders triangles.

**The Solution**: `tri_face_map.bin`

1. **During tessellation** (C++ engine):
   - Index faces deterministically: `[face_0, face_1, ..., face_N]`
   - Tessellate each face independently
   - For each triangle generated, record its source face ID
   - Export combined mesh + uint32 array: `[faceId_tri0, faceId_tri1, ...]`

2. **At runtime** (web viewer):
   - Load mesh.glb and tri_face_map.bin in parallel
   - When feature clicked, get its face IDs: `[12, 77]`
   - Find all triangles where `tri_face_map[i] ∈ {12, 77}`
   - Highlight those triangles

**Why Binary Format**:
- Compact: 4 bytes per triangle
- Fast to parse: Direct TypedArray
- Example: 100K triangles = 400KB (vs ~2MB JSON)

## Feature Recognition Pipeline

```
STEP File
    │
    ├──[1]──> Load Shape (OCCT STEPControl_Reader)
    │
    ├──[2]──> Build AAG (asiAlgo_AAG)
    │          └─> Computes face attributes (surface type, area, normal)
    │          └─> Computes edge attributes (dihedral angle, convexity)
    │          └─> Builds adjacency graph
    │
    ├──[3]──> Run Recognizers (parallel or sequential)
    │          ├─> asiAlgo_RecognizeDrillHoles
    │          │    └─> Finds cylindrical faces
    │          │    └─> Checks internal orientation
    │          │    └─> Validates concave circular edges
    │          │
    │          ├─> asiAlgo_RecognizeShafts
    │          │    └─> Finds external cylinders
    │          │    └─> Checks convex edges
    │          │
    │          ├─> asiAlgo_RecognizeFillets
    │          │    └─> Finds smooth edges (±180°)
    │          │    └─> Validates blend topology
    │          │
    │          └─> asiAlgo_RecognizeCavities
    │               └─> Detects pockets/slots
    │
    ├──[4]──> Tessellate (BRepMesh_IncrementalMesh)
    │          └─> Per-face triangulation
    │          └─> Build tri→face mapping
    │          └─> Export glTF
    │
    └──[5]──> Export Results
               ├─> features.json (feature list with params)
               ├─> aag.json (graph structure)
               └─> meta.json (stats, timings)
```

## Data Schemas

### features.json

```json
{
  "model_id": "uuid",
  "units": "mm",
  "features": [
    {
      "id": "feat_0001",
      "type": "hole",
      "subtype": "simple",
      "faces": [12, 77],
      "edges": [201, 202],
      "params": {
        "diameter_mm": 6.0,
        "depth_mm": 18.2,
        "axis": [0, 0, 1]
      },
      "source": "recognize_holes",
      "confidence": 1.0
    }
  ]
}
```

### aag.json

```json
{
  "nodes": [
    {
      "id": 12,
      "type": "face",
      "surface_type": "cylinder",
      "area_mm2": 339.29,
      "normal": [0, 0, 1]
    }
  ],
  "arcs": [
    {
      "u": 12,
      "v": 77,
      "angle_deg": 90.0,
      "convexity": "concave"
    }
  ]
}
```

### tri_face_map.bin (binary)

```
Header (8 bytes):
  uint32 triangle_count

Data (triangle_count * 4 bytes):
  uint32[] face_ids  // face_id per triangle
```

## Dependencies

### C++ Engine
- **OpenCASCADE 7.8.1** (LGPL-2.1 with exception)
  - CAD kernel (B-rep, STEP import, tessellation)
- **Analysis Situs** (BSD-3-Clause)
  - AAG construction
  - Feature recognizers
- **CMake + Ninja** (build system)

### Python Backend
- **FastAPI** - HTTP API
- **Uvicorn** - ASGI server
- **Pydantic** - Data validation
- **Redis** (optional) - Job queue

### Web Frontend
- **Next.js** - React framework
- **Three.js** - 3D rendering
- **TypeScript** - Type safety

## Build Pipeline

See [core/docs/build-macos.md](../core/docs/build-macos.md) for detailed build instructions.

**Summary**:
1. Build OCCT from source (~20 minutes)
2. Build Analysis Situs SDK (~10 minutes)
3. Build palmetto_engine (~2 minutes)
4. Install Python backend dependencies
5. Install frontend dependencies

## Deployment

**Development**:
```bash
# Terminal 1: C++ engine (already built)
cd core && cmake --build .build/palmetto_engine

# Terminal 2: Python API
cd backend && uvicorn app.main:app --reload

# Terminal 3: Frontend
cd frontend && npm run dev
```

**Production** (Docker):
```dockerfile
# Multi-stage build
FROM ubuntu:22.04 AS builder
# Build OCCT + Analysis Situs + palmetto_engine

FROM python:3.11 AS runtime
# Copy engine binary + Python backend
# Run FastAPI with Gunicorn

FROM node:20 AS frontend
# Build Next.js static site
```

## Performance Targets

| Metric | Target | Notes |
|--------|--------|-------|
| STEP Load | < 1s | For models < 10MB |
| AAG Build | < 2s | Depends on face count |
| Recognition | < 3s | All modules |
| Tessellation | < 1s | Quality 0.35 |
| **Total** | **< 7s** | End-to-end processing |

## Future Enhancements

1. **More Recognizers**:
   - Chamfers
   - Threads
   - Pockets with islands
   - Swept features

2. **Batch Processing**:
   - Process multiple models in parallel
   - Assembly-level recognition

3. **Interactive Editing**:
   - Add/remove features manually
   - Regenerate CAD from feature tree

4. **ML Integration**:
   - Train on labeled data (e.g., MFCAD dataset)
   - Hybrid rule-based + learned approach
