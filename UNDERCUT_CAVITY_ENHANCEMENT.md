# Enhanced Undercut & Cavity/Pocket Analysis

## 🎯 Overview

This document describes the **comprehensive enhancement** to undercut and cavity/pocket recognition for Palmetto's DFM analysis system.

### **Problem Statement**

The original implementation had critical limitations:

1. **Undercut Detection** - Only checked `draft_angle < 0`, which doesn't account for:
   - Volumetric blocking by other geometry
   - Multi-directional tool access for CNC
   - Shadow volumes and occlusion

2. **Cavity/Pocket Analysis** - Lacked:
   - Depth calculation and classification
   - Through-hole vs blind pocket distinction
   - Accessibility metrics (narrow/deep vs wide/shallow)
   - Opening/entrance identification

### **Solution: Dual Analyzer Approach**

We've created **two new specialized analyzers**:

1. **AccessibilityAnalyzer** - Volumetric ray-based undercut detection
2. **PocketDepthAnalyzer** - Enhanced cavity classification with metrics

---

## 📁 New Files Created

### **1. Accessibility Analyzer**
- `accessibility_analyzer.h` - Ray-based undercut and accessibility detection
- `accessibility_analyzer.cpp` - Implementation using Embree ray tracing

### **2. Pocket Depth Analyzer**
- `pocket_depth_analyzer.h` - Depth and classification analysis
- `pocket_depth_analyzer.cpp` - Opening detection and metrics

---

## 🔧 Key Features

### **AccessibilityAnalyzer**

#### **A. Molding Accessibility (True Undercut Detection)**
```cpp
std::map<int, AccessibilityResult> AnalyzeMoldingAccessibility(const gp_Dir& draft_direction);
```

**Algorithm:**
1. Compute face normal and draft angle (geometric)
2. **Cast ray** from face centroid opposite to draft direction
3. If ray hits another face, this is an **undercut** (blocked)
4. Compute **shadow volume** - faces behind other faces
5. Determine if **side action required** (area > 10mm² + severe undercut)

**Output:**
- `is_accessible_molding` - Can be demolded straight?
- `requires_side_action` - Needs lifters/complex tooling?
- `accessibility_score` - 0-1 rating

#### **B. CNC Machining Accessibility**
```cpp
std::map<int, AccessibilityResult> AnalyzeCNCAccessibility();
```

**Algorithm:**
1. Test face accessibility from **6 standard directions** (+/-X, +/-Y, +/-Z)
2. Ray cast from each direction to check visibility
3. Face is accessible if reachable from **at least one direction**
4. Compute score = (accessible_directions / 6)

**Output:**
- `is_accessible_cnc` - Can tool reach this face?
- `accessible_from_direction` - Map of "+X", "-X", etc. → bool
- `accessibility_score` - Percentage of accessible directions

#### **C. Multi-Directional Accessibility Scoring**
```cpp
std::map<int, double> ComputeAccessibilityScores();
```

Tests **26 directions** (cube corners + faces + edges) to compute comprehensive exposure rating.

---

### **PocketDepthAnalyzer**

#### **A. Comprehensive Pocket Analysis**
```cpp
PocketDepthResult AnalyzeSinglePocket(const std::set<int>& face_ids);
```

**Algorithm:**
1. **Find opening faces** - Boundary faces with most external adjacencies
2. **Compute opening plane** - Best-fit plane through opening centroids
3. **Calculate depth** - Maximum distance from opening plane to cavity interior
4. **Estimate opening diameter** - Effective width of entrance
5. **Check through-hole** - Does cavity span >80% of part extent?
6. **Classify type**:
   - `THROUGH_HOLE` - Penetrates completely
   - `BLIND_POCKET` - Closed bottom, 0.5 < AR < 2.0
   - `SHALLOW_RECESS` - AR < 0.5
   - `DEEP_CAVITY` - AR >= 2.0

**Output:**
```cpp
struct PocketDepthResult {
    double depth;                   // Max depth (mm)
    double opening_diameter;        // Entrance width (mm)
    double aspect_ratio;            // depth / opening_diameter
    PocketType type;                // Classification
    bool is_through_hole;           // Penetrates?
    bool is_deep;                   // AR > 2.0
    bool is_narrow;                 // diameter < 5mm
    double accessibility_score;     // 0-1 (machining difficulty)
    std::set<int> opening_faces;    // Entrance faces
    gp_Pnt opening_centroid;        // Center of opening
    gp_Dir opening_normal;          // Direction
};
```

#### **B. Accessibility Scoring**
```cpp
double ComputeAccessibilityScore(double depth, double opening_diameter);
```

**Formula:**
- `aspect_score = 1.0 / (1.0 + AR/2.0)` - Penalty for deep cavities
- `opening_score = min(1.0, diameter/10mm)` - Penalty for narrow openings
- `final_score = (aspect_score + opening_score) / 2.0`

**Interpretation:**
- 1.0 = Easy to machine (wide, shallow)
- 0.5 = Moderate difficulty
- 0.0 = Very difficult (narrow, deep)

---

## 🔌 Integration Steps

### **Step 1: Add to CMakeLists.txt**

```cmake
# In core/CMakeLists.txt, add to PALMETTO_SOURCES:
set(PALMETTO_SOURCES
    # ... existing files ...
    apps/palmetto_engine/accessibility_analyzer.cpp
    apps/palmetto_engine/pocket_depth_analyzer.cpp
)
```

### **Step 2: Update Engine.h**

```cpp
// In core/apps/palmetto_engine/engine.h

#include "accessibility_analyzer.h"
#include "pocket_depth_analyzer.h"

class Engine {
public:
    // Add new DFM methods
    bool analyze_molding_accessibility(const gp_Dir& draft_direction);
    bool analyze_cnc_accessibility();
    bool analyze_pocket_depths();

    // Add getters
    const std::map<int, AccessibilityResult>& get_molding_accessibility() const;
    const std::map<int, AccessibilityResult>& get_cnc_accessibility() const;
    const std::map<int, PocketDepthResult>& get_pocket_depths() const;

private:
    // Add storage
    std::map<int, AccessibilityResult> molding_accessibility_results_;
    std::map<int, AccessibilityResult> cnc_accessibility_results_;
    std::map<int, PocketDepthResult> pocket_depth_results_;
};
```

### **Step 3: Update Engine.cpp**

```cpp
// In core/apps/palmetto_engine/engine.cpp

bool Engine::analyze_molding_accessibility(const gp_Dir& draft_direction) {
    std::cout << "[DFM] Running molding accessibility analysis...\n";

    AccessibilityAnalyzer analyzer(shape_, *aag_);
    molding_accessibility_results_ = analyzer.AnalyzeMoldingAccessibility(draft_direction);

    // Count undercuts
    int undercut_count = 0;
    int side_action_count = 0;
    for (const auto& [face_id, result] : molding_accessibility_results_) {
        if (!result.is_accessible_molding) undercut_count++;
        if (result.requires_side_action) side_action_count++;
    }

    std::cout << "  Found " << undercut_count << " undercut faces\n";
    std::cout << "  " << side_action_count << " require side action/lifters\n";

    return !molding_accessibility_results_.empty();
}

bool Engine::analyze_cnc_accessibility() {
    std::cout << "[DFM] Running CNC accessibility analysis...\n";

    AccessibilityAnalyzer analyzer(shape_, *aag_);
    cnc_accessibility_results_ = analyzer.AnalyzeCNCAccessibility();

    int inaccessible_count = 0;
    for (const auto& [face_id, result] : cnc_accessibility_results_) {
        if (!result.is_accessible_cnc) inaccessible_count++;
    }

    std::cout << "  " << inaccessible_count << " faces inaccessible for machining\n";

    return !cnc_accessibility_results_.empty();
}

bool Engine::analyze_pocket_depths() {
    std::cout << "[DFM] Running pocket depth analysis...\n";

    // Get recognized cavities from cavity_recognizer
    std::vector<std::set<int>> cavity_face_sets;
    for (const auto& feature : features_) {
        if (feature.type == "cavity" || feature.type == "pocket") {
            std::set<int> face_set;
            for (int face_id : feature.face_ids) {
                face_set.insert(face_id);
            }
            cavity_face_sets.push_back(face_set);
        }
    }

    if (cavity_face_sets.empty()) {
        std::cout << "  No cavities found to analyze\n";
        return false;
    }

    PocketDepthAnalyzer analyzer(shape_, *aag_);
    pocket_depth_results_ = analyzer.AnalyzePockets(cavity_face_sets);

    // Print summary
    int through_hole_count = 0;
    int deep_cavity_count = 0;
    for (const auto& [id, result] : pocket_depth_results_) {
        if (result.is_through_hole) through_hole_count++;
        if (result.type == PocketType::DEEP_CAVITY) deep_cavity_count++;
    }

    std::cout << "  " << through_hole_count << " through holes\n";
    std::cout << "  " << deep_cavity_count << " deep cavities\n";

    return !pocket_depth_results_.empty();
}
```

### **Step 4: Update json_exporter.cpp**

```cpp
// In core/apps/palmetto_engine/json_exporter.cpp, around line 586

// Export molding accessibility
auto molding_it = engine_.get_molding_accessibility().find(face_id_0based);
if (molding_it != engine_.get_molding_accessibility().end()) {
    const auto& result = molding_it->second;
    out << ",\n        \"is_undercut\": " << (result.is_accessible_molding ? "false" : "true");
    out << ",\n        \"requires_side_action\": " << (result.requires_side_action ? "true" : "false");
    out << ",\n        \"molding_accessibility_score\": " << std::fixed << std::setprecision(2)
        << result.accessibility_score;
}

// Export CNC accessibility
auto cnc_it = engine_.get_cnc_accessibility().find(face_id_0based);
if (cnc_it != engine_.get_cnc_accessibility().end()) {
    const auto& result = cnc_it->second;
    out << ",\n        \"is_accessible_cnc\": " << (result.is_accessible_cnc ? "true" : "false");
    out << ",\n        \"cnc_accessibility_score\": " << std::fixed << std::setprecision(2)
        << result.accessibility_score;
}

// Export pocket depth metrics (if face belongs to a cavity)
for (const auto& [pocket_id, pocket_result] : engine_.get_pocket_depths()) {
    if (pocket_result.face_ids.count(face_id_0based) > 0) {
        out << ",\n        \"pocket_depth\": " << std::fixed << std::setprecision(2)
            << pocket_result.depth;
        out << ",\n        \"pocket_aspect_ratio\": " << std::fixed << std::setprecision(2)
            << pocket_result.aspect_ratio;
        out << ",\n        \"pocket_type\": " << static_cast<int>(pocket_result.type);
        out << ",\n        \"is_deep_pocket\": " << (pocket_result.is_deep ? "true" : "false");
        out << ",\n        \"is_narrow_pocket\": " << (pocket_result.is_narrow ? "true" : "false");
    }
}
```

### **Step 5: Update main.cpp CLI**

```cpp
// In core/apps/palmetto_engine/main.cpp

if (analyze_dfm_geometry) {
    std::cout << "[3.7/5] Running enhanced DFM geometry analysis...\n";

    // ... existing analyzers ...

    // NEW: Molding accessibility (true undercuts)
    if (!engine.analyze_molding_accessibility(draft_direction)) {
        std::cerr << "WARNING: Molding accessibility analysis failed (continuing)\n";
    }

    // NEW: CNC accessibility
    if (!engine.analyze_cnc_accessibility()) {
        std::cerr << "WARNING: CNC accessibility analysis failed (continuing)\n";
    }

    // NEW: Pocket depth analysis
    if (!engine.analyze_pocket_depths()) {
        std::cerr << "WARNING: Pocket depth analysis failed (continuing)\n";
    }

    std::cout << "  ✓ Enhanced DFM geometry analysis complete\n";
}
```

---

## 🧪 Testing Strategy

### **1. Test Undercut Detection**

Create test models with known undercuts:

**Test Case 1: Simple Negative Draft**
- Model: Block with 10° negative draft face
- Expected: `is_undercut = true`, `requires_side_action = false` (small area)

**Test Case 2: Complex Undercut (Blocked)**
- Model: Part with protruding feature blocking another face
- Expected: `is_undercut = true`, `requires_side_action = true`

**Test Case 3: False Positive Check**
- Model: Angled face with positive draft but facing away
- Expected: `is_undercut = false` (accessible by ray test)

### **2. Test Pocket Depth Analysis**

**Test Case 4: Through Hole**
- Model: Cylinder drilled completely through cube
- Expected: `type = THROUGH_HOLE`, `is_through_hole = true`

**Test Case 5: Blind Pocket**
- Model: 20mm deep pocket with 10mm opening (AR = 2.0)
- Expected: `type = BLIND_POCKET`, `depth ≈ 20mm`, `is_deep = true`

**Test Case 6: Shallow Recess**
- Model: 5mm deep counter bore with 30mm diameter (AR = 0.17)
- Expected: `type = SHALLOW_RECESS`, `is_deep = false`

### **3. Run Tests**

```bash
cd core/.build
cmake --build . --config Release

# Test with simple_block.step
./bin/palmetto_engine \
  --input ../../examples/test-models/simple_block.step \
  --output /tmp/undercut_test \
  --modules all \
  --analyze-dfm-geometry \
  --draft-direction 0,0,1

# Verify AAG exports
jq '.nodes[] | select(.group == "face") | {
  id,
  is_undercut,
  requires_side_action,
  is_accessible_cnc,
  pocket_depth,
  pocket_aspect_ratio
}' /tmp/undercut_test/aag.json | head -30
```

---

## 📊 Expected Performance

| Model Size | Faces | Undercut Analysis | Pocket Depth | Total Time |
|-----------|-------|-------------------|--------------|------------|
| Small | 50 | ~0.5s | ~0.1s | ~0.6s |
| Medium | 200 | ~2s | ~0.5s | ~2.5s |
| Large | 1000 | ~10s | ~2s | ~12s |

**Note:** Embree acceleration critical for performance - without it, ray casting will be **10-100x slower**.

---

## 🎯 New Manufacturing Rules

Update `manufacturing_rules.py` with enhanced rules:

```python
# Molding - True undercut detection
ManufacturingRule(
    name="true_undercut_detected",
    attribute="is_undercut",
    operator="eq",
    threshold=True,
    severity="error",
    message="True undercut detected - face is blocked and cannot be demolded"
),
ManufacturingRule(
    name="side_action_required",
    attribute="requires_side_action",
    operator="eq",
    threshold=True,
    severity="error",
    message="Complex undercut requires side action, lifter, or manual demolding"
),

# CNC Machining - Accessibility
ManufacturingRule(
    name="cnc_inaccessible_face",
    attribute="is_accessible_cnc",
    operator="eq",
    threshold=False,
    severity="error",
    message="Face cannot be reached by cutting tool from any standard direction"
),

# Cavity/Pocket - Deep features
ManufacturingRule(
    name="deep_narrow_pocket",
    attribute="is_deep_pocket",
    operator="eq",
    threshold=True,
    severity="warning",
    message="Deep pocket (AR > 2.0) may require long reach tooling"
),
ManufacturingRule(
    name="high_aspect_ratio_pocket",
    attribute="pocket_aspect_ratio",
    operator="gt",
    threshold=4.0,
    severity="error",
    message="Extreme aspect ratio (> 4.0) - difficult or impossible to machine"
),
```

---

## ✅ Benefits

### **Before (Naive Implementation)**
- ❌ Only geometric draft angle check
- ❌ No volumetric blocking detection
- ❌ No CNC tool access analysis
- ❌ No pocket depth/classification
- ❌ Many false positives/negatives

### **After (Enhanced Implementation)**
- ✅ **True undercut detection** via ray casting
- ✅ **Volumetric obstruction** analysis
- ✅ **Multi-directional tool access** for CNC
- ✅ **Pocket depth + classification** (through/blind/shallow/deep)
- ✅ **Accessibility scores** for machining difficulty
- ✅ **Side action detection** for complex molds
- ✅ **Opening identification** for cavity entrances

---

## 🚀 Next Steps

1. **Compile and test** the new analyzers
2. **Integrate into Engine** (steps 1-5 above)
3. **Update manufacturing rules** with new attributes
4. **Test with real parts** (injection molded, CNC machined)
5. **Validate results** against known undercuts/cavities
6. **Optimize performance** (Embree is critical!)

---

## 📚 References

**Key Algorithms:**
- Ray-based visibility analysis (Computer Graphics standard)
- Shadow volume computation (Silhouette-based obstruction)
- Best-fit plane computation (PCA/least squares)
- Aspect ratio classification (Manufacturing DFM literature)

**Manufacturing Standards:**
- Injection Molding: Draft angles, undercuts, side actions
- CNC Machining: Tool accessibility, deep pockets, aspect ratios
- Design for Manufacturing handbooks (Boothroyd, Dewhurst)
