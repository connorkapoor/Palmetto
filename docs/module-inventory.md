# Analysis Situs Module Inventory

This document catalogs all available feature recognition modules from Analysis Situs that can be integrated into Palmetto.

## Core AAG Module

| Module | File | Description | Headless | Status |
|--------|------|-------------|----------|--------|
| **aag_build** | `asiAlgo_AAG.cpp` | Build Attributed Adjacency Graph | ✓ | ✓ Integrated |

**Implementation**: `asiAlgo_AAG::Build(TopoDS_Shape)`

**Outputs**:
- Face nodes with attributes (surface type, area, normal, etc.)
- Edge attributes (dihedral angle, convexity, smoothness)
- Adjacency arcs (face-to-face relationships)

**Required**: All recognizers depend on AAG being built first.

---

## Feature Recognizers

### 1. Drill Holes

| Module | Files | Description | Headless | Status |
|--------|-------|-------------|----------|--------|
| **recognize_holes** | `asiAlgo_RecognizeDrillHoles.cpp`<br>`asiAlgo_RecognizeDrillHolesRule.cpp` | Detect drilled holes (simple, countersunk, counterbored) | ✓ | 🔄 In Progress |

**Implementation**: `asiAlgo_RecognizeDrillHoles`

**Algorithm**:
1. Find cylindrical faces (seeds)
2. Check if internal (normal points toward axis)
3. Validate concave circular concentric edges
4. Collect coaxial cylinders (counterbored)
5. Detect coaxial cones (countersunk)

**Output Features**:
- Simple hole (single cylinder)
- Countersunk hole (cylinder + cone)
- Counterbored hole (multiple coaxial cylinders)

**Parameters**:
- `diameter_mm`: Hole diameter
- `depth_mm`: Hole depth
- `axis`: Hole axis direction [x, y, z]
- `through`: Boolean (through hole vs blind)

---

### 2. Shafts

| Module | Files | Description | Headless | Status |
|--------|-------|-------------|----------|--------|
| **recognize_shafts** | `asiAlgo_RecognizeShafts.cpp`<br>`asiAlgo_RecognitionRuleShaft.cpp` | Detect cylindrical shafts and bosses | ✓ | 🔄 In Progress |

**Implementation**: `asiAlgo_RecognizeShafts`

**Algorithm**:
1. Find cylindrical faces
2. Check if external (normal points away from axis)
3. Validate convex edges (material addition)
4. Collect coaxial cylinders (stepped shafts)

**Output Features**:
- Simple shaft (single cylinder)
- Stepped shaft (multiple coaxial cylinders)
- Boss (short shaft protrusion)

**Parameters**:
- `diameter_mm`: Shaft diameter
- `length_mm`: Shaft length
- `axis`: Shaft axis direction
- `stepped`: Boolean (stepped vs uniform)

---

### 3. Edge-Based Features (EBF) - Fillets & Blends

| Module | Files | Description | Headless | Status |
|--------|-------|-------------|----------|--------|
| **recognize_ebf** | `asiAlgo_RecognizeEBF.cpp`<br>`asiAlgo_RecognizeBlends.cpp` | Detect edge-based fillets and blends | ✓ | 🔄 In Progress |

**Implementation**: `asiAlgo_RecognizeEBF`

**Algorithm** (from source):
1. Find smooth edges (dihedral angle ≈ ±180°)
2. Check face is cylindrical or toroidal
3. Validate blend topology (connects two support faces)
4. Filter by radius threshold
5. Group blends into chains

**Output Features**:
- Constant-radius fillet (cylindrical)
- Variable-radius fillet (conical)
- Blends (toroidal)

**Parameters**:
- `radius_mm`: Fillet radius
- `type`: "constant" | "variable"
- `length_mm`: Fillet length

**Analysis Situs Reference**:
- Fillets recognized via smooth edge detection
- Uses `asiAlgo_FindSmoothEdges` internally
- Distinguishes from holes using angle type (tangent vs sharp concave)

---

### 4. Cavities

| Module | Files | Description | Headless | Status |
|--------|-------|-------------|----------|--------|
| **recognize_cavities** | `asiAlgo_RecognizeCavities.cpp`<br>`asiAlgo_RecognizeCavitiesRule.cpp` | Detect pockets, slots, and depressions | ✓ | 🔄 In Progress |

**Implementation**: `asiAlgo_RecognizeCavities`

**Algorithm**:
1. Find concave face groups (material removal)
2. Classify topology:
   - **Pocket**: Closed depression (bottom + vertical walls)
   - **Slot**: Through-cavity (no bottom, parallel walls)
   - **Blind cavity**: Partial depth
3. Extract geometric parameters

**Output Features**:
- Rectangular pocket
- Circular pocket
- Through slot
- Blind slot

**Parameters**:
- `width_mm`, `length_mm`, `depth_mm`
- `shape`: "rectangular" | "circular" | "irregular"
- `through`: Boolean

---

### 5. Isolated Features

| Module | Files | Description | Headless | Status |
|--------|-------|-------------|----------|--------|
| **recognize_isolated** | `asiAlgo_RecognizeIsolated.cpp` | Detect isolated feature faces | ✓ | ⏸️ Not Started |

**Implementation**: `asiAlgo_RecognizeIsolated`

**Description**:
Identifies faces that are topologically isolated (disconnected from main body).
Useful for detecting manufacturing errors or separate components.

---

### 6. Probes

| Module | Files | Description | Headless | Status |
|--------|-------|-------------|----------|--------|
| **recognize_probes** | `asiAlgo_RecognizeProbes.cpp` | Detect probe features | ✓ | ⏸️ Not Started |

**Implementation**: `asiAlgo_RecognizeProbes`

**Description**:
Specialized recognizer for probe-like geometric features.
(Further analysis needed to determine exact use case)

---

### 7. Convex Hull

| Module | Files | Description | Headless | Status |
|--------|-------|-------------|----------|--------|
| **recognize_convex_hull** | `asiAlgo_RecognizeConvexHull.cpp` | Compute and recognize convex hull | ✓ | ⏸️ Not Started |

**Implementation**: `asiAlgo_RecognizeConvexHull`

**Description**:
Computes the convex hull of the shape.
Useful for stock material identification and machining planning.

---

## Supporting Algorithms

### Dihedral Angle Computation

| Module | File | Description | Headless | Status |
|--------|------|-------------|----------|--------|
| **check_dihedral_angle** | `asiAlgo_CheckDihedralAngle.cpp` | Compute signed dihedral angles | ✓ | ✓ Integrated |

**Key Method**: `asiAlgo_CheckDihedralAngle::Compute()`

**Algorithm** (Line 353):
```cpp
angleRad = TF.AngleWithRef(TG, Ref);
if (angleRad < 0) → CONVEX (material addition, shaft/boss)
else → CONCAVE (material removal, hole/pocket)
```

**Critical for**:
- Hole vs shaft distinction
- Fillet vs hole distinction
- Feature orientation

---

### Smooth Edge Detection

| Module | File | Description | Headless | Status |
|--------|------|-------------|----------|--------|
| **find_smooth_edges** | `asiAlgo_FindSmoothEdges` (part of EBF) | Identify smooth/tangent edges | ✓ | ✓ Integrated |

**Tolerance**: 3° (default in Analysis Situs)

**Angle Types**:
- `FeatureAngleType_Smooth`: |angle| ≈ 180°
- `FeatureAngleType_SmoothConvex`: angle ≈ -180°
- `FeatureAngleType_SmoothConcave`: angle ≈ +180°
- `FeatureAngleType_Convex`: angle < -3°
- `FeatureAngleType_Concave`: angle > +3°

---

## Integration Status

| Priority | Module | Status | Notes |
|----------|--------|--------|-------|
| 🥇 P0 | AAG Build | ✓ Done | Core dependency |
| 🥇 P0 | Dihedral Angle | ✓ Done | Core dependency |
| 🥈 P1 | Drill Holes | 🔄 In Progress | Main use case |
| 🥈 P1 | Shafts | 🔄 In Progress | Hole complement |
| 🥈 P1 | Fillets (EBF) | 🔄 In Progress | Common feature |
| 🥉 P2 | Cavities | 🔄 In Progress | Pockets/slots |
| 🥉 P2 | Isolated | ⏸️ Not Started | Quality check |
| ⚪ P3 | Probes | ⏸️ Not Started | Specialized |
| ⚪ P3 | Convex Hull | ⏸️ Not Started | Manufacturing planning |

---

## Module Dependencies

```
ALL RECOGNIZERS
      ↓
   AAG Build (asiAlgo_AAG)
      ↓
  ┌─────┴─────┐
  │           │
Dihedral   Surface
 Angle      Attributes
  │           │
  └─────┬─────┘
        ↓
 Feature Recognizers
  ├─> Holes
  ├─> Shafts
  ├─> Fillets (EBF)
  ├─> Cavities
  └─> Others
```

---

## API Reference (Simplified)

### AAG Build

```cpp
#include <asiAlgo_AAG.h>

Handle(asiAlgo_AAG) aag = new asiAlgo_AAG();
bool success = aag->Build(shape);  // TopoDS_Shape

int numNodes = aag->GetNumberOfNodes();
int numArcs = aag->GetNumberOfArcs();
```

### Hole Recognizer

```cpp
#include <asiAlgo_RecognizeDrillHoles.h>

Handle(asiAlgo_AAG) aag = /* ... */;
asiAlgo_RecognizeDrillHoles recognizer(aag);

bool success = recognizer.Perform();

// Get results
const std::vector<asiAlgo_Feature>& holes = recognizer.GetFeatures();

for (const auto& hole : holes) {
    // hole.GetFaceIndices()
    // hole.GetDiameter()
    // hole.GetDepth()
    // hole.GetAxis()
}
```

### Shaft Recognizer

```cpp
#include <asiAlgo_RecognizeShafts.h>

asiAlgo_RecognizeShafts recognizer(aag);
recognizer.Perform();

const std::vector<asiAlgo_Feature>& shafts = recognizer.GetFeatures();
```

### Fillet Recognizer (EBF)

```cpp
#include <asiAlgo_RecognizeEBF.h>

asiAlgo_RecognizeEBF recognizer(aag);
recognizer.SetMaxRadius(10.0);  // Max fillet radius in mm
recognizer.Perform();

const std::vector<asiAlgo_Feature>& fillets = recognizer.GetFeatures();
```

---

## Next Steps for Integration

1. ✅ **Build OCCT** - Foundation CAD kernel
2. 🔄 **Build Analysis Situs SDK** - Recognizer libraries
3. 🔄 **Link palmetto_engine** - Integrate recognizers one by one
4. ⏸️ **Test on real models** - Validate each recognizer
5. ⏸️ **Add remaining recognizers** - Cavities, isolated, etc.

---

## References

- **Analysis Situs Website**: https://analysissitus.org
- **Source Code**: https://gitlab.com/ssv/AnalysisSitus
- **Documentation**: https://analysissitus.org/features.html
- **Recognizers Overview**: https://analysissitus.org/features/feature-recognition.html
