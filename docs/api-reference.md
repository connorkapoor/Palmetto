# Palmetto API Reference

## Overview

Palmetto provides a RESTful API for CAD feature recognition. All endpoints return JSON responses and use standard HTTP status codes.

**Base URL:** `http://localhost:8000`

**API Version:** 1.0

## Authentication

Currently, no authentication is required. Future versions may implement API key authentication.

## Common Response Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 201 | Created |
| 400 | Bad Request (validation error) |
| 404 | Not Found |
| 422 | Unprocessable Entity (invalid data) |
| 500 | Internal Server Error |

## Error Response Format

```json
{
  "detail": "Error message describing what went wrong"
}
```

---

## Upload Endpoints

### Upload CAD File

Upload a STEP, IGES, or BREP file for analysis.

**Endpoint:** `POST /api/upload`

**Content-Type:** `multipart/form-data`

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| file | File | Yes | CAD file (.step, .stp, .iges, .igs, .brep) |

**Request Example (curl):**

```bash
curl -X POST http://localhost:8000/api/upload \
  -F "file=@/path/to/model.step"
```

**Request Example (Python):**

```python
import requests

with open('model.step', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/api/upload',
        files={'file': f}
    )

data = response.json()
model_id = data['model_id']
```

**Request Example (JavaScript):**

```javascript
const formData = new FormData();
formData.append('file', fileInput.files[0]);

const response = await fetch('http://localhost:8000/api/upload', {
  method: 'POST',
  body: formData
});

const data = await response.json();
const modelId = data.model_id;
```

**Response (200 OK):**

```json
{
  "model_id": "a1b2c3d4-5e6f-7g8h-9i0j-k1l2m3n4o5p6",
  "filename": "bracket.step",
  "file_format": "step",
  "topology_stats": {
    "vertices": 24,
    "edges": 36,
    "faces": 14,
    "shells": 1,
    "solids": 1
  },
  "upload_time": "2025-01-15T10:30:00Z",
  "file_size_bytes": 524288
}
```

**Errors:**

- `400`: File format not supported
- `413`: File too large (>100MB)
- `422`: Invalid or corrupted CAD file

---

## Recognition Endpoints

### List Available Recognizers

Get a list of all registered feature recognizers.

**Endpoint:** `GET /api/recognition/recognizers`

**Request Example:**

```bash
curl http://localhost:8000/api/recognition/recognizers
```

**Response (200 OK):**

```json
{
  "recognizers": [
    {
      "name": "hole_detector",
      "description": "Detects drilled holes including simple, countersunk, counterbored, and threaded holes",
      "feature_types": [
        "hole_simple",
        "hole_countersunk",
        "hole_counterbored",
        "hole_threaded"
      ],
      "parameters": {
        "min_diameter": {
          "type": "float",
          "default": 0.0,
          "description": "Minimum hole diameter in mm"
        },
        "max_diameter": {
          "type": "float",
          "default": null,
          "description": "Maximum hole diameter in mm (null = unlimited)"
        },
        "hole_types": {
          "type": "array",
          "default": null,
          "description": "Filter by hole types (null = all types)"
        }
      }
    },
    {
      "name": "shaft_detector",
      "description": "Detects cylindrical shaft features (protruding cylinders)",
      "feature_types": ["shaft"],
      "parameters": {
        "min_diameter": {"type": "float", "default": 0.0},
        "max_diameter": {"type": "float", "default": null}
      }
    },
    {
      "name": "fillet_detector",
      "description": "Detects rounded blend features (fillets and rounds)",
      "feature_types": ["fillet"],
      "parameters": {
        "min_radius": {"type": "float", "default": 0.0},
        "max_radius": {"type": "float", "default": null}
      }
    },
    {
      "name": "cavity_detector",
      "description": "Detects cavity features including blind pockets, through cavities, and slots",
      "feature_types": ["cavity_blind", "cavity_through", "slot"],
      "parameters": {
        "min_volume": {"type": "float", "default": 0.0}
      }
    }
  ],
  "count": 4
}
```

---

### Recognize Features

Run a specific recognizer on an uploaded model.

**Endpoint:** `POST /api/recognition/recognize`

**Content-Type:** `application/json`

**Request Body:**

```json
{
  "model_id": "a1b2c3d4-5e6f-7g8h-9i0j-k1l2m3n4o5p6",
  "recognizer": "hole_detector",
  "parameters": {
    "min_diameter": 5.0,
    "max_diameter": 20.0
  }
}
```

**Request Example (curl):**

```bash
curl -X POST http://localhost:8000/api/recognition/recognize \
  -H "Content-Type: application/json" \
  -d '{
    "model_id": "a1b2c3d4-5e6f-7g8h-9i0j-k1l2m3n4o5p6",
    "recognizer": "hole_detector",
    "parameters": {"min_diameter": 5.0}
  }'
```

**Request Example (Python):**

```python
import requests

response = requests.post(
    'http://localhost:8000/api/recognition/recognize',
    json={
        'model_id': model_id,
        'recognizer': 'hole_detector',
        'parameters': {
            'min_diameter': 5.0,
            'max_diameter': 20.0
        }
    }
)

features = response.json()['features']
```

**Response (200 OK):**

```json
{
  "model_id": "a1b2c3d4-5e6f-7g8h-9i0j-k1l2m3n4o5p6",
  "recognizer": "hole_detector",
  "recognized_intent": {
    "recognizer": "hole_detector",
    "parameters": {
      "min_diameter": 5.0,
      "max_diameter": 20.0
    },
    "confidence": 1.0
  },
  "features": [
    {
      "feature_id": "feat_001",
      "feature_type": "hole_simple",
      "confidence": 0.95,
      "face_ids": ["face_abc123", "face_def456"],
      "properties": {
        "diameter": 10.0,
        "radius": 5.0,
        "depth": 25.0,
        "axis": [0.0, 0.0, 1.0],
        "center": [50.0, 50.0, 0.0],
        "is_through": false
      },
      "bounding_geometry": null,
      "metadata": {
        "recognizer": "hole_detector",
        "algorithm_version": "1.0",
        "timestamp": "2025-01-15T10:35:00Z"
      }
    },
    {
      "feature_id": "feat_002",
      "feature_type": "hole_countersunk",
      "confidence": 0.88,
      "face_ids": ["face_ghi789", "face_jkl012", "face_mno345"],
      "properties": {
        "diameter": 8.0,
        "depth": 15.0,
        "countersink_diameter": 16.0,
        "countersink_angle": 90.0,
        "axis": [0.0, 1.0, 0.0],
        "is_through": true
      },
      "bounding_geometry": null,
      "metadata": {
        "recognizer": "hole_detector",
        "algorithm_version": "1.0"
      }
    }
  ],
  "execution_time": 0.234,
  "timestamp": "2025-01-15T10:35:00Z"
}
```

**Errors:**

- `404`: Model ID not found
- `400`: Invalid recognizer name
- `422`: Invalid parameters for recognizer

---

## Natural Language Interface

### Parse and Execute Natural Language Command

Parse a natural language command and execute the appropriate recognizer.

**Endpoint:** `POST /api/nl/parse`

**Content-Type:** `application/json`

**Request Body:**

```json
{
  "model_id": "a1b2c3d4-5e6f-7g8h-9i0j-k1l2m3n4o5p6",
  "command": "find all holes larger than 10mm"
}
```

**Request Example (curl):**

```bash
curl -X POST http://localhost:8000/api/nl/parse \
  -H "Content-Type: application/json" \
  -d '{
    "model_id": "a1b2c3d4-5e6f-7g8h-9i0j-k1l2m3n4o5p6",
    "command": "find all holes larger than 10mm"
  }'
```

**Request Example (Python):**

```python
response = requests.post(
    'http://localhost:8000/api/nl/parse',
    json={
        'model_id': model_id,
        'command': 'find all fillets with radius less than 2mm'
    }
)

features = response.json()['features']
```

**Response (200 OK):**

Same format as `/api/recognition/recognize` response, with additional `recognized_intent` field showing how the command was parsed:

```json
{
  "model_id": "a1b2c3d4-5e6f-7g8h-9i0j-k1l2m3n4o5p6",
  "recognizer": "hole_detector",
  "recognized_intent": {
    "recognizer": "hole_detector",
    "parameters": {
      "min_diameter": 10.0
    },
    "confidence": 0.95,
    "original_command": "find all holes larger than 10mm"
  },
  "features": [...],
  "execution_time": 0.456
}
```

**Example Commands:**

| Command | Parsed Intent |
|---------|---------------|
| "find all holes" | `hole_detector` with default parameters |
| "find holes larger than 10mm" | `hole_detector` with `min_diameter: 10.0` |
| "detect fillets" | `fillet_detector` with default parameters |
| "show me shafts between 5 and 15mm" | `shaft_detector` with `min_diameter: 5.0, max_diameter: 15.0` |
| "find small fillets under 2mm radius" | `fillet_detector` with `max_radius: 2.0` |

**Errors:**

- `404`: Model ID not found
- `400`: Could not parse command or map to recognizer
- `422`: Parsed parameters are invalid

---

## Export Endpoints

### Export to glTF

Export a model to glTF format with optional feature highlighting.

**Endpoint:** `POST /api/export/gltf`

**Content-Type:** `application/json`

**Request Body:**

```json
{
  "model_id": "a1b2c3d4-5e6f-7g8h-9i0j-k1l2m3n4o5p6",
  "linear_deflection": 0.1,
  "angular_deflection": 0.5,
  "feature_highlights": {
    "feat_001": {"color": [0.0, 0.5, 1.0], "intensity": 1.0},
    "feat_002": {"color": [1.0, 0.0, 0.0], "intensity": 0.8}
  }
}
```

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| model_id | string | Yes | - | Model identifier from upload |
| linear_deflection | float | No | 0.1 | Maximum distance between mesh and surface (smaller = finer mesh) |
| angular_deflection | float | No | 0.5 | Maximum angular deviation in degrees (smaller = finer mesh) |
| feature_highlights | object | No | {} | Map of feature_id to highlight color/intensity |

**Request Example (Python):**

```python
response = requests.post(
    'http://localhost:8000/api/export/gltf',
    json={
        'model_id': model_id,
        'linear_deflection': 0.05,  # Finer mesh
        'feature_highlights': {
            'feat_001': {'color': [0.0, 0.5, 1.0], 'intensity': 1.0}
        }
    }
)

# Save binary glTF file
with open('model.glb', 'wb') as f:
    f.write(response.content)
```

**Response (200 OK):**

Binary glTF (.glb) file stream with:
- Tessellated mesh geometry
- Vertex positions, normals, colors
- Face-to-triangle mapping in `extras.face_map`
- Feature highlights in `extras.feature_highlights`

**Content-Type:** `application/octet-stream`

**Content-Disposition:** `attachment; filename="{filename}.glb"`

**glTF Extras Format:**

The exported glTF includes metadata in the `extras` field:

```json
{
  "extras": {
    "face_map": {
      "face_abc123": [0, 1, 2, 15, 16, 17],
      "face_def456": [3, 4, 5, 6, 7, 8]
    },
    "feature_highlights": {
      "feat_001": {
        "color": [0.0, 0.5, 1.0],
        "intensity": 1.0,
        "face_ids": ["face_abc123", "face_def456"]
      }
    },
    "model_id": "a1b2c3d4-5e6f-7g8h-9i0j-k1l2m3n4o5p6",
    "export_timestamp": "2025-01-15T10:40:00Z"
  }
}
```

**Errors:**

- `404`: Model ID not found
- `422`: Invalid tessellation parameters

---

## Model Management

### List Models

Get all models currently in memory.

**Endpoint:** `GET /api/models`

**Response (200 OK):**

```json
{
  "models": [
    {
      "model_id": "a1b2c3d4-5e6f-7g8h-9i0j-k1l2m3n4o5p6",
      "filename": "bracket.step",
      "file_format": "step",
      "upload_time": "2025-01-15T10:30:00Z",
      "last_accessed": "2025-01-15T10:40:00Z",
      "topology_stats": {
        "vertices": 24,
        "edges": 36,
        "faces": 14
      }
    }
  ],
  "count": 1
}
```

---

### Get Model Info

Get detailed information about a specific model.

**Endpoint:** `GET /api/models/{model_id}`

**Response (200 OK):**

```json
{
  "model_id": "a1b2c3d4-5e6f-7g8h-9i0j-k1l2m3n4o5p6",
  "filename": "bracket.step",
  "file_format": "step",
  "upload_time": "2025-01-15T10:30:00Z",
  "last_accessed": "2025-01-15T10:40:00Z",
  "file_size_bytes": 524288,
  "topology_stats": {
    "vertices": 24,
    "edges": 36,
    "faces": 14,
    "shells": 1,
    "solids": 1
  },
  "aag_stats": {
    "total_nodes": 75,
    "total_edges": 124,
    "face_surface_types": {
      "plane": 8,
      "cylinder": 4,
      "fillet": 2
    }
  }
}
```

---

### Delete Model

Remove a model from memory.

**Endpoint:** `DELETE /api/models/{model_id}`

**Response (200 OK):**

```json
{
  "message": "Model deleted successfully",
  "model_id": "a1b2c3d4-5e6f-7g8h-9i0j-k1l2m3n4o5p6"
}
```

---

## Data Types

### FeatureType Enum

```
hole_simple
hole_countersunk
hole_counterbored
hole_threaded
shaft
cavity_blind
cavity_through
slot
fillet
chamfer
boss
pocket
step
rib
```

### RecognizedFeature Object

```json
{
  "feature_id": "string",
  "feature_type": "FeatureType",
  "confidence": 0.0-1.0,
  "face_ids": ["string"],
  "properties": {
    // Feature-specific properties
  },
  "bounding_geometry": null,
  "metadata": {
    "recognizer": "string",
    "timestamp": "ISO8601 datetime"
  }
}
```

### Common Feature Properties

**Holes:**
- `diameter`: float (mm)
- `radius`: float (mm)
- `depth`: float (mm)
- `axis`: [x, y, z] direction vector
- `center`: [x, y, z] position
- `is_through`: boolean

**Shafts:**
- `diameter`: float (mm)
- `length`: float (mm)
- `axis`: [x, y, z]

**Fillets:**
- `radius`: float (mm)
- `length`: float (mm) - arc length
- `blend_type`: "edge" | "face"

**Cavities:**
- `volume`: float (mm³)
- `depth`: float (mm)
- `floor_area`: float (mm²)
- `is_through`: boolean

---

## Complete Workflow Example

### Python Client Example

```python
import requests
import json

BASE_URL = 'http://localhost:8000'

# Step 1: Upload CAD file
print("Uploading CAD file...")
with open('bracket.step', 'rb') as f:
    upload_response = requests.post(
        f'{BASE_URL}/api/upload',
        files={'file': f}
    )

upload_data = upload_response.json()
model_id = upload_data['model_id']
print(f"Model ID: {model_id}")
print(f"Topology: {upload_data['topology_stats']}")

# Step 2: List available recognizers
recognizers_response = requests.get(f'{BASE_URL}/api/recognition/recognizers')
recognizers = recognizers_response.json()['recognizers']
print(f"\nAvailable recognizers: {[r['name'] for r in recognizers]}")

# Step 3: Use natural language to find features
print("\nFinding holes...")
nl_response = requests.post(
    f'{BASE_URL}/api/nl/parse',
    json={
        'model_id': model_id,
        'command': 'find all holes larger than 5mm'
    }
)

nl_data = nl_response.json()
features = nl_data['features']
print(f"Found {len(features)} holes")
print(f"Execution time: {nl_data['execution_time']:.2f}s")

# Print feature details
for feature in features:
    print(f"\nFeature: {feature['feature_type']}")
    print(f"  Confidence: {feature['confidence']:.2%}")
    print(f"  Diameter: {feature['properties']['diameter']:.2f}mm")
    print(f"  Depth: {feature['properties']['depth']:.2f}mm")

# Step 4: Run specific recognizer with parameters
print("\nDetecting fillets...")
fillet_response = requests.post(
    f'{BASE_URL}/api/recognition/recognize',
    json={
        'model_id': model_id,
        'recognizer': 'fillet_detector',
        'parameters': {
            'max_radius': 3.0
        }
    }
)

fillets = fillet_response.json()['features']
print(f"Found {len(fillets)} small fillets (≤3mm)")

# Step 5: Export to glTF with highlighting
print("\nExporting to glTF...")
export_response = requests.post(
    f'{BASE_URL}/api/export/gltf',
    json={
        'model_id': model_id,
        'linear_deflection': 0.05,
        'feature_highlights': {
            feature['feature_id']: {
                'color': [0.0, 0.5, 1.0],
                'intensity': 1.0
            }
            for feature in features
        }
    }
)

# Save glTF file
with open('bracket_highlighted.glb', 'wb') as f:
    f.write(export_response.content)

print("Export complete! Open bracket_highlighted.glb in a glTF viewer.")

# Step 6: Cleanup
requests.delete(f'{BASE_URL}/api/models/{model_id}')
print("\nModel deleted from memory.")
```

### JavaScript/React Example

```javascript
// Upload file
const uploadFile = async (file) => {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch('http://localhost:8000/api/upload', {
    method: 'POST',
    body: formData
  });

  return await response.json();
};

// Natural language query
const findFeatures = async (modelId, command) => {
  const response = await fetch('http://localhost:8000/api/nl/parse', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model_id: modelId,
      command: command
    })
  });

  return await response.json();
};

// Export to glTF
const exportToGLTF = async (modelId, featureHighlights) => {
  const response = await fetch('http://localhost:8000/api/export/gltf', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model_id: modelId,
      feature_highlights: featureHighlights
    })
  });

  return await response.blob();
};

// Usage in React component
const CADAnalyzer = () => {
  const [modelId, setModelId] = useState(null);
  const [features, setFeatures] = useState([]);

  const handleUpload = async (event) => {
    const file = event.target.files[0];
    const data = await uploadFile(file);
    setModelId(data.model_id);
  };

  const handleNLQuery = async (command) => {
    const data = await findFeatures(modelId, command);
    setFeatures(data.features);
  };

  return (
    <div>
      <input type="file" onChange={handleUpload} accept=".step,.stp,.iges,.igs" />
      <input
        type="text"
        placeholder="e.g., find all holes"
        onKeyPress={(e) => e.key === 'Enter' && handleNLQuery(e.target.value)}
      />
      <ul>
        {features.map(f => (
          <li key={f.feature_id}>
            {f.feature_type}: Ø{f.properties.diameter}mm
          </li>
        ))}
      </ul>
    </div>
  );
};
```

---

## Rate Limits

Currently no rate limits are enforced. For production deployment, consider:
- Max 100 requests per minute per IP
- Max 10 concurrent uploads
- Max 50 models per user in memory

---

## OpenAPI Documentation

Interactive API documentation is available at:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

---

## Versioning

Current API version: **v1**

Future versions will use URL versioning:
- v1: `/api/upload`
- v2: `/api/v2/upload`

---

## Support

For issues, feature requests, or questions:
- GitHub Issues: [Your repository URL]
- Email: [Your email]
- Documentation: http://localhost:8000/docs
