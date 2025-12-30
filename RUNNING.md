# Palmetto - Currently Running! 🚀

## Status: ✅ LIVE

Both the backend and frontend are running and ready to use!

### Running Services

| Service | Status | URL | Details |
|---------|--------|-----|---------|
| **Backend API** | ✅ Running | http://localhost:8001 | FastAPI with 4 recognizers loaded |
| **Frontend UI** | ✅ Running | http://localhost:5173 | React + Vite dev server |
| **API Docs** | ✅ Available | http://localhost:8001/docs | Interactive Swagger UI |
| **pythonOCC** | ✅ Installed | v7.7.2 | CAD file loading enabled |

### Quick Access

**Main Application:**
👉 **http://localhost:5173**

**API Documentation:**
👉 **http://localhost:8001/docs**

## How to Use

### 1. Upload a CAD File

1. Open http://localhost:5173 in your browser
2. Click the file upload area or drag & drop a STEP/IGES file
3. Supported formats: `.step`, `.stp`, `.iges`, `.igs`, `.brep`

**Need test files?** See `examples/test-models/README.md` for where to download free CAD models.

### 2. Recognize Features

After uploading, you have two options:

#### Option A: Natural Language Query
In the "Natural Language Query" box, type commands like:
- `find all holes`
- `find holes larger than 10mm`
- `detect fillets`
- `show me shafts`

Click "Recognize" to run the query.

#### Option B: Direct Recognizer (Coming Soon)
Use the recognizer selector to choose a specific recognizer with parameters.

### 3. View Results

- Recognized features appear in the "Recognition Results" panel
- Click a feature to highlight it in the 3D viewer (blue highlighting)
- Features show:
  - Feature type (hole, shaft, fillet, cavity)
  - Confidence score
  - Properties (diameter, depth, radius, etc.)
  - Number of faces

### 4. Explore 3D Model

- **Rotate**: Left-click and drag
- **Pan**: Right-click and drag
- **Zoom**: Scroll wheel

## Available Recognizers

1. **hole_detector** - Detects drilled holes
   - Simple holes
   - Countersunk holes
   - Counterbored holes
   - Threaded holes

2. **shaft_detector** - Detects cylindrical shafts
   - Protruding cylinders
   - Bosses

3. **fillet_detector** - Detects rounded blends
   - Edge fillets
   - Face blends

4. **cavity_detector** - Detects cavities and pockets
   - Blind pockets
   - Through cavities
   - Slots

## Example Queries

Try these natural language commands:

```
find all holes
find holes larger than 5mm
detect small fillets under 3mm
show me all shafts
find countersunk holes
detect all features
```

## Background Task IDs

Backend: `b83a0e4`
Frontend: `b3ade42`

## Stopping the Servers

To stop the servers, you can:
1. Press Ctrl+C in each terminal window, OR
2. Ask me to kill the background tasks

## Troubleshooting

### Upload works but export fails
- ✅ **FIXED** - Frontend now uses Vite proxy correctly

### CAD file won't load
- Check file format is supported (.step, .stp, .iges, .igs, .brep)
- Make sure file is valid CAD format (not corrupted)
- Check backend logs for errors

### 3D viewer shows nothing
- Export may have failed - check browser console
- Model may be very small/large - try zooming
- Check that glTF export completed successfully

### No features detected
- Model may not contain the queried features
- Try a different recognizer
- Check confidence thresholds

## Development

### Backend Logs
View backend output:
```bash
tail -f /tmp/claude/-Users-connorkapoor-Desktop-Palmetto/tasks/b83a0e4.output
```

### Frontend Logs
View frontend output:
```bash
tail -f /tmp/claude/-Users-connorkapoor-Desktop-Palmetto/tasks/b3ade42.output
```

### Restart Backend
```bash
cd /Users/connorkapoor/Desktop/Palmetto/backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

### Restart Frontend
```bash
cd /Users/connorkapoor/Desktop/Palmetto/frontend
npm run dev
```

## Next Steps

1. **Get Test Files**: Download some STEP files from GrabCAD or McMaster-Carr
2. **Upload & Test**: Try uploading a mechanical part with holes/fillets
3. **Query Features**: Use natural language to find features
4. **Explore Results**: Click features to highlight them in 3D

## Documentation

- **API Reference**: See `docs/api-reference.md`
- **Adding Recognizers**: See `docs/recognizers.md`
- **AAG Specification**: See `docs/aag-specification.md`
- **Main README**: See `README.md`

---

**Ready to test!** Open http://localhost:5173 and upload your first CAD file! 🎉
