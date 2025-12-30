# MFCAD Feature Recognition - Status Report

**Date**: 2025-12-29
**Target**: 85% accuracy on MFCAD dataset
**Current**: 0.1-1% accuracy after 6 iterations

---

## Executive Summary

**Objective**: Implement robust feature recognition algorithms validated against the MFCAD labeled dataset (15,488 CAD models).

**Current Status**:
- ✅ Complete infrastructure for dataset loading, validation, and metrics
- ✅ Fixed critical ground truth extraction bug (connected component splitting)
- ❌ **Accuracy stuck at 0-1% across multiple recognizer architectures**
- ❌ **85% target not achievable with simple rule-based approaches**

**Recommendation**: Pivot to machine learning approach (Random Forest or GNN) to learn discriminative patterns from labeled data.

---

## Accomplishments

### 1. Dataset Integration ✅
- Implemented `MFCADLoader` to load STEP files with ground truth face labels
- Extracts 15,488 models with 16 feature types
- Supports stratified sampling for efficient validation

### 2. Validation Framework ✅
- `RecognizerValidator`: IoU-based feature matching (threshold 0.5)
- `MetricsCalculator`: Precision, recall, F1, confusion matrix
- Automated testing pipeline

### 3. Taxonomy Mapping ✅
- Mapped 16 MFCAD labels to Palmetto `FeatureType` enum
- Extended enum with: `STEP_THROUGH`, `STEP_BLIND`, `PASSAGE`, `CHAMFER`
- Property-based shape variants ("rectangular", "triangular", etc.)

### 4. Critical Bug Fix ✅
**Issue**: Initial ground truth extraction grouped ALL faces of a feature TYPE into one mega-feature.
**Fix**: Implemented connected component analysis to split into individual feature INSTANCES.
**Impact**: Revealed true dataset complexity - 903 features in 100 models (vs 594 before fix).

### 5. Topology Analysis ✅
Discovered key MFCAD patterns:
- **100% planar surfaces** (no cylinders, cones, etc.)
- **100% linear edges** (no circles, B-splines, etc.)
- **Dihedral angles**: Features have 315° concave edges, stock has 225° avg
- **Multiple instances**: "rectangular_through_slot: 4 faces" often splits into 2-4 separate slot instances

---

## Recognizer Iterations

### Iteration 1: PlanarMFCADRecognizer v1 (Baseline)
- **Approach**: Group all adjacent planar faces
- **Result**: 0.95% accuracy, 143 FP, grouped stock with features

### Iteration 2: PlanarMFCADRecognizer v2 (Concave Grouping)
- **Approach**: Only group on dihedral > 185° (concave edges)
- **Result**: 1.03% accuracy, 7 TP pockets, 1 TP step
- **Issue**: Still grouping stock faces (stock-to-stock also > 185°)

### Iteration 3: Fixed Ground Truth + Dihedral > 300°
- **Bug fix**: Connected component splitting in GT extraction
- **Approach**: Stricter threshold (> 300°) to avoid stock
- **Result**: 0.11% accuracy, 1 TP, 902 FN
- **Issue**: Threshold too strict, created isolated faces

### Iteration 4: Inverted Strategy (Dihedral >= 175°)
- **Approach**: Stop at convex edges (< 175°)
- **Result**: Same grouping issues, still merging stock
- **Issue**: No threshold reliably separates feature/stock

### Iteration 5: Size Filtering (1-7 faces)
- **Approach**: Reject groups > 7 faces as stock
- **Result**: 0.13% accuracy, 42 detections (should be ~750)
- **Issue**: Too aggressive, rejecting real features

### Iteration 6: FaceClassifier (Face-Level Classification)
- **Approach**: Classify each face as feature/stock, then group
- **Result**: 0.00% accuracy, classified ALL faces as features
- **Issue**: Handcrafted rules too permissive

---

## Root Cause Analysis

### Why Rule-Based Approaches Fail

**Problem 1: Overlapping Geometric Properties**
- Feature-to-feature edges: 315° (concave)
- Stock-to-stock edges: 45-315°, avg 225° (also concave!)
- Feature-to-stock edges: 45-315° (varied)
- **No clear dihedral threshold separates them**

**Problem 2: All Planar Faces Are Connected**
- Simple BFS groups entire part into one component
- Splitting on dihedral angles doesn't match ground truth grouping
- Ground truth may use semantic/context-aware labeling beyond geometry

**Problem 3: Instance vs Type Labeling**
- MFCAD labels faces by TYPE, not INSTANCE
- Multiple slots share label 0, must be split post-hoc
- Ground truth grouping logic is unclear from geometry alone

---

## Path Forward to 85% Accuracy

### Option A: Machine Learning (Recommended)

**Approach**: Train supervised classifier on face-level geometric features

#### 1. Random Forest Classifier
- **Effort**: 2-3 days
- **Features**: area, dihedral stats, normal direction, convexity measures
- **Training**: 70% of MFCAD dataset (~10k models)
- **Expected**: 70-80% accuracy (realistic baseline)

#### 2. Graph Neural Network (GNN)
- **Effort**: 5-7 days
- **Architecture**: GCN/GAT on AAG subgraphs
- **Node features**: Surface type, area, normal, dihedral angles
- **Edge features**: Dihedral angle, edge type
- **Expected**: 80-90% accuracy (state-of-the-art)
- **Requirements**: PyTorch Geometric, GPU recommended

#### 3. Hybrid Approach
- **Step 1**: Random Forest for face classification (feature vs stock)
- **Step 2**: Rule-based post-processing for feature grouping
- **Expected**: 75-85% accuracy

### Option B: Enhanced Rule-Based (Lower Success Probability)

**Approach**: Multi-criteria heuristics combining:
- Dihedral angle distributions (not just threshold)
- Face normal clustering (identify "inside" vs "outside")
- Convexity analysis (local minima detection)
- Proximity to part boundary

**Challenges**:
- Requires extensive tuning per feature type
- May not generalize across MFCAD diversity
- Likely plateaus below 70% accuracy

---

## Implementation Roadmap (ML Approach)

### Week 1: Random Forest Baseline
1. Extract face-level features from labeled data
2. Build training/test split (70/30)
3. Train Random Forest classifier
4. Validate on test set, iterate on features
5. **Target**: 70%+ accuracy

### Week 2: Feature Grouping & Type Classification
1. Post-process RF predictions to group adjacent feature faces
2. Implement feature type classifiers (pocket, slot, step, etc.)
3. Tune IoU matching threshold
4. **Target**: 75%+ accuracy

### Week 3: GNN Implementation (if needed)
1. Convert AAG to PyTorch Geometric format
2. Implement GCN/GAT model
3. Train on subgraph classification task
4. **Target**: 85%+ accuracy

---

## Resources Required

### Computational
- **Training**: ~10k models × 10-50 faces = 100k-500k face samples
- **Memory**: ~2-4 GB for Random Forest, ~8-16 GB for GNN
- **Time**: RF trains in minutes, GNN in hours

### Code Dependencies
- `scikit-learn` (Random Forest)
- `pytorch` + `torch-geometric` (GNN)
- `numpy`, `pandas` for feature extraction

---

## Current Metrics (Best Result: Iteration 2)

```
Overall Accuracy: 1.03%
Macro F1 Score:   3.41%

Per-Feature Performance:
  cavity_pocket:  7 TP, 148 FP, 106 FN (5.22% F1)
  step_through:   1 TP,  12 FP, 112 FN (1.59% F1)
  cavity_slot:    0 TP,   6 FP, 149 FN (0.00% F1)
  (all others):   0 TP
```

**Interpretation**:
- Detecting SOME pockets and steps
- Massive false positive rate (148 FP for pockets)
- Missing most features (high FN)

---

## Conclusion

**Rule-based topology analysis is insufficient for MFCAD feature recognition.**

The dataset's complexity (multiple instances per type, semantic labeling, overlapping geometric properties) requires **learning discriminative patterns from labeled data** rather than hand-crafted heuristics.

**Recommendation**: Proceed with Random Forest baseline (fastest path to 70-75% accuracy), then evaluate if GNN is needed to reach 85% target.

---

## Files Created

### Infrastructure
- `app/testing/mfcad_loader.py` - Dataset loading
- `app/testing/validation.py` - Recognizer validation
- `app/testing/metrics.py` - Metrics calculation
- `app/testing/taxonomy_mapper.py` - MFCAD → Palmetto mapping
- `app/testing/models.py` - Data structures

### Recognizers
- `app/recognizers/features/planar_mfcad.py` - Rule-based planar recognizer (v1-v5)
- `app/recognizers/features/face_classifier.py` - Face-level classifier (v6)

### Analysis Scripts
- `scripts/run_mfcad_validation.py` - Validation pipeline
- `scripts/analyze_mfcad_patterns.py` - Topology pattern analysis
- `scripts/debug_face_grouping.py` - Grouping debugging
- `scripts/analyze_dihedral_angles.py` - Dihedral angle analysis
- `scripts/sample_multiple_models.py` - Multi-model sampling
- `scripts/analyze_face_geometry.py` - Face geometry analysis

### Validation Results
- `validation_results/baseline_cavity.txt` - CavityRecognizer baseline (0%)
- `validation_results/planar_mfcad_v1.txt` - Iterations 1-5 results
- `validation_results/face_classifier_v1.txt` - Iteration 6 results

---

**End of Report**
