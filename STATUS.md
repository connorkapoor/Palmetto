# Palmetto C++ Integration - Status Report

**Date**: December 29, 2025
**Goal**: Replace Python feature recognizers with proven C++ Analysis Situs recognizers

---

## ✅ Completed

### 1. Project Structure (100%)
- [x] Created monorepo structure with `core/` directory
- [x] Added Analysis Situs as git submodule (BSD-3-Clause)
- [x] Created `THIRD_PARTY_NOTICES.md` with proper licensing
- [x] Set up directory structure: apps/, scripts/, docs/, third_party/

### 2. OCCT Build (100%)
- [x] Created `build_occt_macos.sh` script
- [x] Successfully built OCCT 7.8.1 from source
- [x] Installed to `core/.local/occt/`
- [x] Created symlinks for backward compatibility (TKSTEP → TKDESTEP)
- [x] Verified: `libTKernel.dylib` present

**Location**: `/Users/connorkapoor/Desktop/Palmetto/core/.local/occt/`

### 3. C++ Engine Code (100%)
- [x] `main.cpp` - CLI interface with --input, --outdir, --modules options
- [x] `engine.h/cpp` - Core recognition engine scaffolding
- [x] `json_exporter.h/cpp` - JSON export for features, AAG, metadata
- [x] `version.h` - Version information
- [x] `CMakeLists.txt` - Build configuration

**Location**: `/Users/connorkapoor/Desktop/Palmetto/core/apps/palmetto_engine/`

**Note**: Current engine code has stubs - needs integration with real Analysis Situs APIs once library build completes.

### 4. FastAPI Integration (100%)
- [x] Created `cpp_engine.py` - Python wrapper to call C++ binary via subprocess
- [x] Created `analyze.py` - New API endpoints for C++ engine
- [x] Updated `main.py` - Registered new analyze router
- [x] Endpoints created:
  - `POST /api/analyze/upload` - Upload STEP file
  - `POST /api/analyze/process` - Run C++ engine analysis
  - `GET /api/analyze/{model_id}/artifacts/{filename}` - Download results
  - `GET /api/analyze/modules` - List available recognizers
  - `GET /api/analyze/health` - Check C++ engine status

**Location**: `/Users/connorkapoor/Desktop/Palmetto/backend/`

### 5. Documentation (100%)
- [x] `architecture.md` - Complete system architecture
- [x] `module-inventory.md` - Catalog of all Analysis Situs recognizers
- [x] `build-macos.md` - macOS build instructions

**Location**: `/Users/connorkapoor/Desktop/Palmetto/docs/`

---

## 🔄 In Progress

### 6. Analysis Situs Build (~20%)
- [x] Created `build_analysis_situs_macos.sh` script
- [x] Downloaded Eigen 3.4.0 (header-only)
- [x] Downloaded RapidJSON 1.1.0 (header-only)
- [x] Configured CMake with `DISTRIBUTION_TYPE=Algo` (headless SDK)
- [x] Fixed OCCT library name mismatch (TKSTEP → TKDESTEP symlinks)
- [ ] Build in progress - estimated 5-10 minutes

**Current Status**: Building C++ algorithm libraries...

**Expected Output**: `libTKASIAlgo.dylib` in `core/.local/analysis_situs/lib/`

---

## ⏸️ Not Started

### 7. Wire Up First Recognizer (0%)
**Blockers**: Waiting for Analysis Situs build to complete

**Tasks**:
- [ ] Update `engine.cpp` to call real Analysis Situs APIs
- [ ] Implement `run_hole_recognizer()` with `asiAlgo_RecognizeDrillHoles`
- [ ] Implement tessellation with tri→face mapping
- [ ] Export glTF with `tinygltf` library
- [ ] Write `tri_face_map.bin` as uint32 array
- [ ] Test end-to-end with a sample STEP file

**Files to Update**:
- `core/apps/palmetto_engine/engine.cpp` (replace stubs)
- `core/CMakeLists.txt` (link Analysis Situs libraries)

### 8. Update Frontend (0%)
**Blockers**: Needs working C++ engine first

**Tasks**:
- [ ] Update Three.js viewer to load `mesh.glb`
- [ ] Load `tri_face_map.bin` into Uint32Array
- [ ] Implement feature → triangle highlighting
- [ ] Update API calls to use `/api/analyze/` endpoints
- [ ] Display feature properties (diameter, depth, etc.)
- [ ] Add feature list UI component

**Files to Update**:
- `frontend/src/components/ModelViewer.tsx`
- `frontend/src/api/client.ts`

---

## Key Technical Decisions

### Triangle→Face Mapping
**Problem**: Analysis Situs operates on B-rep faces, web viewer renders triangles.

**Solution**:
1. C++ engine tessellates each face independently
2. Records which face produced each triangle
3. Exports `tri_face_map.bin`: `[uint32 faceId0, uint32 faceId1, ...]`
4. Frontend loads mapping in parallel with mesh
5. When feature clicked (e.g., faces [12, 77]), find all triangles where `map[i] ∈ {12, 77}`
6. Highlight those triangles

**Why Binary**: Compact (4 bytes/triangle), fast to parse, ~400KB for 100K triangles

### OCCT Library Changes
**Issue**: OCCT 7.8.1 renamed/consolidated STEP libraries.

**Old** (Analysis Situs expects):
- TKSTEP, TKSTEP209, TKSTEPAttr, TKSTEPBase

**New** (OCCT 7.8.1 provides):
- TKDESTEP (consolidated Data Exchange STEP module)

**Fix**: Created symlinks for backward compatibility:
```bash
ln -s libTKDESTEP.dylib libTKSTEP.dylib
ln -s libTKDESTEP.dylib libTKSTEP209.dylib
# ... etc
```

---

## Next Actions (Priority Order)

1. **Wait for Analysis Situs build to complete** (~5 min)
   - Monitor `/tmp/asitus_build2.log`
   - Verify `libTKASIAlgo.dylib` is created

2. **Integrate Analysis Situs APIs into C++ engine**
   - Replace stub functions with real recognizer calls
   - Implement proper tessellation with face mapping
   - Add glTF export (may need tinygltf library)

3. **Build palmetto_engine binary**
   - `cd core && mkdir -p .build/palmetto_engine && cd .build/palmetto_engine`
   - `cmake -G Ninja ../.. && ninja`
   - Test with `./palmetto_engine --help`

4. **Test end-to-end with sample STEP file**
   - Run: `./palmetto_engine --input test.step --outdir out/ --modules all`
   - Verify outputs: `mesh.glb`, `tri_face_map.bin`, `features.json`, `aag.json`, `meta.json`
   - Check feature count and types

5. **Integrate with FastAPI**
   - Set `PALMETTO_ENGINE_PATH` environment variable
   - Start backend: `cd backend && uvicorn app.main:app --reload`
   - Test upload and analysis endpoints

6. **Update frontend for C++ engine**
   - Modify API client to use `/api/analyze/` endpoints
   - Implement tri→face mapping highlighting
   - Test feature visualization

---

## Architecture Summary

```
┌─────────────┐
│   Browser   │  React + Three.js
│             │  - Loads mesh.glb
│             │  - Loads tri_face_map.bin
│             │  - Highlights triangles by feature
└──────┬──────┘
       │ HTTP/JSON
       ▼
┌─────────────┐
│  FastAPI    │  Python Backend
│  Backend    │  - /api/analyze/upload
│             │  - /api/analyze/process
│             │  - Wraps C++ engine via subprocess
└──────┬──────┘
       │ subprocess call
       ▼
┌─────────────┐
│ palmetto_   │  C++ Engine (headless)
│   engine    │  - Loads STEP (OCCT)
│             │  - Builds AAG (Analysis Situs)
│             │  - Runs recognizers (holes, shafts, fillets, cavities)
│             │  - Generates mesh + tri→face mapping
│             │  - Exports JSON + glTF + binary mapping
└─────────────┘
        │
        ├─> mesh.glb (3D model)
        ├─> tri_face_map.bin (triangle → face mapping)
        ├─> features.json (recognized features)
        ├─> aag.json (topology graph)
        └─> meta.json (stats, timings)
```

---

## Performance Targets

| Stage | Target | Notes |
|-------|--------|-------|
| STEP Load | < 1s | For models < 10MB |
| AAG Build | < 2s | Face/edge analysis |
| Recognition | < 3s | All modules |
| Tessellation | < 1s | Quality 0.35 |
| **Total** | **< 7s** | End-to-end |

---

## Success Criteria

- [x] OCCT builds on macOS
- [ ] Analysis Situs SDK builds (headless)
- [ ] C++ engine compiles and links
- [ ] Engine recognizes holes in test STEP file
- [ ] FastAPI can call engine and return results
- [ ] Frontend displays mesh with feature highlighting
- [ ] Clicking feature highlights correct triangles

---

## Build Commands Reference

### OCCT
```bash
cd /Users/connorkapoor/Desktop/Palmetto/core
./scripts/build_occt_macos.sh
```

### Analysis Situs
```bash
cd /Users/connorkapoor/Desktop/Palmetto/core
./scripts/build_analysis_situs_macos.sh
```

### Palmetto Engine
```bash
cd /Users/connorkapoor/Desktop/Palmetto/core
mkdir -p .build/palmetto_engine
cd .build/palmetto_engine
cmake -G Ninja -DCMAKE_PREFIX_PATH="../../.local/occt;../../.local/analysis_situs" ../..
ninja
```

### Backend
```bash
cd /Users/connorkapoor/Desktop/Palmetto/backend
export PALMETTO_ENGINE_PATH=/Users/connorkapoor/Desktop/Palmetto/core/.build/palmetto_engine/bin/palmetto_engine
uvicorn app.main:app --reload
```

### Frontend
```bash
cd /Users/connorkapoor/Desktop/Palmetto/frontend
npm run dev
```

---

## Links

- **Analysis Situs Website**: https://analysissitus.org
- **Source**: https://gitlab.com/ssv/AnalysisSitus
- **OCCT**: https://dev.opencascade.org
- **glTF**: https://www.khronos.org/gltf/

---

**Last Updated**: December 29, 2025, 1:30 PM
