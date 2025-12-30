# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Palmetto is a CAD feature recognition tool with graph-based analysis using the Attributed Adjacency Graph (AAG) methodology from Analysis Situs. The architecture is hybrid: C++ engine for CAD processing and feature recognition, Python FastAPI backend for API/orchestration, and React frontend for visualization.

## Architecture: Three-Layer System

### 1. C++ Engine (`core/`)
The core feature recognition engine built with OpenCASCADE and Analysis Situs algorithms.

**Key Components:**
- **AAG (Attributed Adjacency Graph)**: Graph structure representing B-Rep topology with geometric attributes
  - Nodes = faces with surface type, area, normal vectors, cylinder/torus parameters
  - Edges = adjacency relationships with dihedral angles (signed: negative=convex, positive=concave, ±180°=smooth)
  - Used by all feature recognizers for graph traversal

- **Feature Recognizers**: Independent modules that traverse AAG to detect manufacturing features
  - `hole_recognizer`: Detects cylindrical holes (simple, countersunk, counterbored)
  - `cavity_recognizer`: Finds pockets/recesses using concave edge propagation
  - `fillet_recognizer`: Identifies toroidal blend surfaces
  - `chamfer_recognizer`: Detects beveled edges
  - Each outputs Feature objects with face_ids and geometric parameters

- **Build Output**: Single `palmetto_engine` binary that processes STEP files → AAG JSON + glTF mesh + tri_face_map

**CRITICAL Dihedral Angle Convention** (frequently misunderstood):
```cpp
// In AAG::ComputeDihedralAngle:
if (angle < 0) {
    edge.is_convex = true;    // NEGATIVE = CONVEX (material bends inward)
} else {
    edge.is_concave = true;   // POSITIVE = CONCAVE (material bends outward)
}
if (abs(angle) > 177.0) {
    edge.is_smooth = true;    // Near ±180° = tangent/continuous
}
```
When implementing cavity/pocket detection, seed from faces with ≥60% concave (positive angle) edges.

### 2. Python Backend (`backend/`)
FastAPI server that orchestrates the C++ engine and provides REST API.

**Data Flow:**
1. Upload STEP file → saved to `data/{model_id}/input.step`
2. Call C++ engine: `palmetto_engine --input input.step --output output/ --modules all`
3. Engine generates:
   - `output/aag.json` - Full AAG graph with features
   - `output/mesh.glb` - Tessellated mesh
   - `output/tri_face_map.bin` - Triangle→Face ID mapping for click selection
   - `output/topology.json` - Topological metadata
4. API serves artifacts and feature data to frontend

**Key Routes:**
- `/api/analyze/upload` - Upload STEP file
- `/api/analyze/process` - Run C++ engine with specified modules
- `/api/analyze/{model_id}/artifacts/{file}` - Serve generated files
- `/api/query/execute` - Natural language geometric queries (uses Claude API)
- `/api/aag/{model_id}/graph` - Fetch AAG for graph visualization

**C++ Engine Integration** (`app/core/cpp_engine.py`):
```python
# Engine path resolution:
# 1. Check env PALMETTO_ENGINE_PATH
# 2. Fall back to backend/../core/.build/bin/palmetto_engine
# 3. Must be built before backend can run
```

### 3. React Frontend (`frontend/`)
3D visualization with feature highlighting and natural language query interface.

**Key Components:**
- `Viewer3D`: Three.js canvas with glTF rendering + face click selection
  - Loads mesh.glb + tri_face_map.bin to enable triangle→face mapping
  - Highlights faces by changing material color on click/selection
- `AAGGraphViewer`: Force-directed graph visualization of AAG topology
- `ScriptingPanel`: Natural language query UI (bottom panel)
  - "show faces with area 20mm²" → backend parses with Claude API → returns face IDs
  - "find cavities" → queries AAG for faces marked `is_cavity_face: true`
- `ResultsPanel`: Sidebar showing detected features, click to highlight

**Apple Glass UI Style:**
All panels use glassmorphism:
```css
background: rgba(255, 255, 255, 0.7);
backdrop-filter: blur(20px) saturate(180%);
border: 1px solid rgba(255, 255, 255, 0.3);
border-radius: 16px;
```

## Development Workflow

### C++ Engine Development

**Build from scratch:**
```bash
cd core
mkdir -p .build && cd .build
cmake .. -DCMAKE_PREFIX_PATH=/opt/homebrew/Cellar/opencascade/7.8.1_1  # macOS Homebrew OCCT
cmake --build . --config Release
# Binary at: .build/bin/palmetto_engine
```

**Rebuild after code changes:**
```bash
cd core/.build
cmake --build . --config Release
```

**Test engine directly:**
```bash
cd core/.build
./bin/palmetto_engine --help
./bin/palmetto_engine --version
./bin/palmetto_engine --list-modules

# Process a test file:
./bin/palmetto_engine \
  --input ../../examples/test-models/simple_block.step \
  --output /tmp/test_output \
  --modules all \
  --mesh-quality 0.35
```

**Add new recognizer:**
1. Create `apps/palmetto_engine/my_feature_recognizer.{h,cpp}`
2. Implement recognition logic using AAG graph traversal
3. Add to `CMakeLists.txt` source list
4. Register in `engine.cpp` with CLI flag
5. Rebuild and test

### Backend Development

**Setup:**
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Create .env file:
cat > .env << EOF
ANTHROPIC_API_KEY=your_key_here
CORS_ORIGINS=http://localhost:5173
EOF
```

**Run server:**
```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Or with environment variable for engine path:
PALMETTO_ENGINE_PATH=/path/to/palmetto_engine uvicorn app.main:app --reload
```

**Test endpoints:**
```bash
# Health check (verifies C++ engine connectivity):
curl http://localhost:8000/health

# Upload and analyze:
curl -X POST http://localhost:8000/api/analyze/upload \
  -F "file=@examples/test-models/simple_block.step"
# Returns: {"model_id": "...", "filename": "..."}

curl -X POST http://localhost:8000/api/analyze/process \
  -H "Content-Type: application/json" \
  -d '{"model_id": "xxx", "modules": "all", "mesh_quality": 0.35}'
```

**Code quality:**
```bash
black .           # Format
ruff check .      # Lint
mypy app          # Type check
pytest            # Run tests
```

### Frontend Development

**Setup:**
```bash
cd frontend
npm install
```

**Run dev server:**
```bash
npm run dev
# Opens http://localhost:5173
# Vite proxy forwards /api/* to http://localhost:8000
```

**Build for production:**
```bash
npm run build
# Output in dist/
npm run preview  # Preview production build
```

**Code quality:**
```bash
npm run lint     # ESLint
npm run format   # Prettier
```

## Common Development Tasks

### Testing End-to-End Feature Recognition

1. Build C++ engine:
   ```bash
   cd core/.build && cmake --build . --config Release
   ```

2. Start backend (in separate terminal):
   ```bash
   cd backend && source .venv/bin/activate
   uvicorn app.main:app --reload
   ```

3. Start frontend (in separate terminal):
   ```bash
   cd frontend && npm run dev
   ```

4. Upload test model in browser at http://localhost:5173
5. Check browser console and backend logs for recognition results

### Debugging "No Features Detected"

Common issues:
- **Wrong angle interpretation**: Remember negative=convex, positive=concave in AAG
- **Thresholds too strict**: Check recognizer validation criteria (e.g., cavity size limits)
- **AAG construction failed**: Check backend logs for C++ engine errors
- **Module not enabled**: Verify `--modules all` or specific module name in analyze request

Add debug logging to recognizer:
```cpp
// In recognize() method:
std::cout << "  [DEBUG] Found " << seed_faces.size() << " seed faces\n";
std::cout << "  [DEBUG] Propagated to " << cavity_faces.size() << " faces\n";
std::cout << "  [DEBUG] Validation: " << (is_valid ? "PASS" : "FAIL") << "\n";
```

Rebuild and check backend logs when processing.

### Adding Natural Language Query Support for New Feature

1. **C++ side**: Mark faces in `json_exporter.cpp`:
   ```cpp
   // In ExportAAGToJSON, face export loop:
   std::set<int> myFeatureFaceIds;  // populate from features
   if (myFeatureFaceIds.count(i) > 0) {
       out << ",\n        \"is_my_feature_face\": true";
   }
   ```

2. **Backend side**: Add query examples in `backend/app/query/query_parser.py`:
   ```python
   # Add to LLM prompt examples:
   User: "find my features"
   Assistant: {{
       "entity_type": "face",
       "predicates": [{{"attribute": "is_my_feature_face", "operator": "eq", "value": true}}]
   }}

   # Add to fallback parser:
   if "my feature" in query_lower and entity_type == "face":
       predicates.append(Predicate(attribute="is_my_feature_face", operator=Operator.EQ, value=True))
   ```

3. Test query in ScriptingPanel UI

## File Locations Reference

**C++ Engine:**
- Main: `core/apps/palmetto_engine/main.cpp`
- AAG: `core/apps/palmetto_engine/aag.{h,cpp}`
- Recognizers: `core/apps/palmetto_engine/*_recognizer.{h,cpp}`
- Build config: `core/CMakeLists.txt`
- Binary output: `core/.build/bin/palmetto_engine`

**Backend:**
- Entry point: `backend/app/main.py`
- C++ engine wrapper: `backend/app/core/cpp_engine.py`
- Analysis routes: `backend/app/api/routes/analyze.py`
- Query parser: `backend/app/query/query_parser.py`
- Model storage: `backend/data/{model_id}/`

**Frontend:**
- App root: `frontend/src/App.tsx`
- 3D viewer: `frontend/src/components/Viewer3D.tsx`
- Query UI: `frontend/src/components/ScriptingPanel.tsx`
- API client: `frontend/src/api/client.ts`
- Config: `frontend/vite.config.ts` (proxy to backend)

## Known Pitfalls

1. **Port mismatch**: Vite proxy must target backend port (default 8000, not 8001)
   - Fix in `frontend/vite.config.ts`: `target: 'http://localhost:8000'`

2. **Engine not found**: Backend can't find C++ binary
   - Set `PALMETTO_ENGINE_PATH` or build to default location
   - Check `/health` endpoint to verify engine connectivity

3. **Angle sign errors in recognizers**: Most common bug
   - Always review AAG angle convention before implementing propagation logic
   - Test with simple geometry (single pocket/fillet) first

4. **Mesh/tri_face_map mismatch**: Click selection broken
   - Ensure both mesh.glb and tri_face_map.bin are from same engine run
   - Check `topology.json` has matching face count

5. **CORS errors**: Frontend can't reach backend
   - Verify CORS_ORIGINS in backend .env includes http://localhost:5173
   - Check browser console for specific CORS error message

## OpenCASCADE (OCCT) Notes

The C++ engine uses OCCT 7.8.x. Key classes:
- `TopoDS_Shape/Face/Edge`: Topological entities
- `BRepAdaptor_Surface`: Access underlying geometry (plane, cylinder, etc.)
- `TopExp_Explorer`: Traverse topology (iterate faces, edges)
- `GProp_GProps`: Compute properties (area, inertia)
- `BRepMesh_IncrementalMesh`: Tessellation for glTF export

On macOS with Homebrew: `brew install opencascade`
CMake finds via: `CMAKE_PREFIX_PATH=/opt/homebrew/Cellar/opencascade/7.8.1_1`

## Data Flow Summary

```
User uploads STEP file
  ↓
Frontend → POST /api/analyze/upload → Backend saves to data/{model_id}/input.step
  ↓
Frontend → POST /api/analyze/process → Backend calls C++ engine
  ↓
C++ engine: STEP → AAG → Feature Recognition → JSON + glTF + tri_face_map
  ↓
Backend returns feature list + artifact URLs
  ↓
Frontend fetches mesh.glb, tri_face_map.bin, topology.json
  ↓
Viewer3D renders mesh, ResultsPanel shows features
  ↓
User clicks feature → Frontend highlights faces via tri_face_map
  ↓
User types NL query → Backend parses with Claude API → Returns matching entities
  ↓
Frontend highlights query results in 3D view
```
