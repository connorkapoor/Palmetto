# GNN Feature Recognition - Final Report

**Date**: 2025-12-29
**Objective**: Achieve 85% accuracy on MFCAD feature recognition using Graph Neural Networks
**Status**: ❌ **FAILED - 0% Instance-Level Accuracy**

---

## Executive Summary

Attempted GNN-based feature recognition on MFCAD dataset. Despite achieving **80.2% F1 score on face-level classification**, the approach **failed completely at instance-level recognition (0% accuracy)**.

**Root cause**: Fundamental mismatch between training (sparse labels) and inference (dense predictions) + poor grouping algorithm.

---

## Timeline

### Day 1: Initial Implementation
- ✅ Installed PyTorch Geometric
- ✅ Created AAG → PyG graph converter
- ✅ Built MFCAD graph dataset
- ✅ Implemented GAT architecture (204k params)
- ✅ Trained for 50 epochs
- ✅ Achieved 79.8% F1 (reported as success)

### Day 2: Validation & Bug Discovery
- ❌ End-to-end validation: **0% accuracy**
- 🔍 Investigation revealed **CRITICAL BUG**: Graphs had **0 edges**
- 🐛 **Bug**: Graph converter looked for wrong relationship name
  - Searched for: `"face_adjacent_face"`
  - Actual name: `"adjacent"`
  - Result: All graphs were node-only (no message passing!)

### Day 2: Retrain with Fixed Edges
- ✅ Fixed edge extraction bug
- ✅ Retrained GNN with proper graph structure
- ✅ Achieved 80.2% F1 (slight improvement)
- ❌ End-to-end validation: **Still 0% accuracy**

### Day 2: Root Cause Analysis
- Model predicts **100% of faces as features** (extreme class 0 bias)
- Grouping algorithm merges ALL adjacent feature faces into one blob
- Ground truth has 5-10 separate features per model
- Predicted: 1 giant feature per model
- IoU matching: Complete failure

---

## Technical Details

### Architecture
**Graph Attention Network (GAT)**
```
Input: 12D node features (normals, dihedrals, area, etc.)
       2D edge features (dihedral angle, edge type)

Layers:
- 3 GATv2Conv layers (4 attention heads each)
- Batch normalization + 30% dropout
- Binary classifier (feature vs stock)

Parameters: 204,194
```

### Training Configuration
```python
Dataset:     1000 MFCAD models (stratified sample)
Split:       700 train, 300 test
Batch Size:  8 graphs
Epochs:      50 (best at epoch 1)
Optimizer:   Adam (lr=0.001)
Loss:        Cross-entropy (masked to labeled nodes only)
```

### Training Results
```
Face-Level Classification (on labeled nodes):
- Test F1:        80.2%
- Test Accuracy:  66.9%
- Test Precision: 66.4%
- Test Recall:    100.0% ⚠️ (Perfect recall = red flag)

Confusion Matrix (labeled faces only):
  TP: 951  |  FN: 0    ← Perfect recall
  FP: 482  |  TN: ?
```

### Inference Results
```
Instance-Level Recognition (full test set):
- Overall Accuracy:  0.00%
- Macro Precision:   0.00%
- Macro Recall:      0.00%
- Macro F1:          0.00%

Per-Type Performance:
  cavity_pocket:  0 TP,   0 FP, 217 FN
  cavity_slot:    0 TP,   0 FP, 737 FN
  step_blind:     0 TP,   0 FP, 141 FN
  step_through:   0 TP,   0 FP, 105 FN
  chamfer:        0 TP,   0 FP,  68 FN
  passage:        0 TP,   0 FP,  56 FN

Total: 0/1624 correct (100% failure rate)
```

---

## Why GNN Failed

### Problem 1: Sparse Labels in MFCAD
**Ground truth labeling**: Only 5-30% of faces are labeled in each model
- Example: 19 total faces → 2 labeled features, 3 labeled stock, **14 unlabeled**
- Training masks unlabeled faces correctly
- But evaluation metrics only on labeled subset

**Consequence**: 80% F1 is misleading - it's on a tiny subset of faces

### Problem 2: Model Bias Toward Class 0
**Observation**: Model predicts **100% of planar faces as features**
- Training recall: 100% (never predicts class 1)
- Logits heavily skewed: Class 0 mean=+0.23, Class 1 mean=-0.35
- Probabilities: ~63% confidence for class 0 on ALL faces

**Cause**: Likely class imbalance in labeled data favors features over stock

### Problem 3: Naive Grouping Algorithm
**Current approach**: BFS on all predicted feature faces
```python
def _group_adjacent_faces(faces):
    # Groups ALL adjacent faces into connected components
    # Result: ONE giant blob per model
```

**Problem**: No boundary detection
- Doesn't recognize when one feature ends and another begins
- Merges pockets + slots + steps + chamfers into one mega-feature
- Ground truth: 5-10 separate features
- Predicted: 1 massive feature

### Problem 4: IoU Matching Failure
**IoU threshold**: 0.5 (Intersection over Union)

**Example**:
- Ground truth: `[slot_1: {f1,f2,f3}, slot_2: {f4,f5}, pocket: {f6,f7,f8}]`
- Predicted: `[giant_blob: {f1,f2,f3,f4,f5,f6,f7,f8}]`

**IoU calculation**:
- `IoU(giant_blob, slot_1) = 3/8 = 0.375` ❌ Below threshold
- `IoU(giant_blob, slot_2) = 2/8 = 0.250` ❌ Below threshold
- `IoU(giant_blob, pocket) = 3/8 = 0.375` ❌ Below threshold

**Result**: Zero matches despite detecting correct faces!

---

## Critical Bugs Found & Fixed

### Bug 1: Zero Edges in Graphs ⚠️ CRITICAL
**Impact**: GAT architecture completely broken
- Graph Attention Networks REQUIRE edges for message passing
- All training was on node-only graphs (no graph structure!)
- Model learned ONLY from node features, not topology

**Symptoms**:
```python
# Debug output:
Graph info:
  Nodes: 19
  Edges: 0        ← Should be ~90!
  Node features: 12
```

**Root Cause**:
```python
# graph_converter.py (WRONG)
if edge.relationship.value == "face_adjacent_face":  # Never matches!

# Actual AAG edge relationship name:
edge.relationship.value == "adjacent"
```

**Fix**:
```python
# Changed to correct relationship name
if edge.relationship.value == "adjacent":
```

**After fix**:
```
Graph info:
  Nodes: 19
  Edges: 90  ✓
```

### Bug 2: Model Path Resolution
**Issue**: Incorrect relative path to model checkpoint
```python
# WRONG: Goes to app/models/ (doesn't exist)
model_path = Path(__file__).parent.parent.parent / "models"

# CORRECT: Goes to backend/models/
model_path = Path(__file__).parent.parent.parent.parent / "models"
```

---

## Why 80% F1 Didn't Translate to 0% Accuracy

### Training vs Inference Mismatch

**Training** (on labeled subset):
```
Model sees: 5 faces total
  2 labeled as feature (class 0)
  3 labeled as stock (class 1)

Loss computed only on these 5 faces
Metrics computed only on these 5 faces
F1 = 80% looks great!
```

**Inference** (on all faces):
```
Model sees: 19 faces total
  Predicts: 19 as feature (100% class 0)
  Groups: 19 faces → 1 blob

Ground truth has: 3 separate features
Predicted: 1 giant feature
IoU matching: 0/3 ❌
```

### The Death Spiral
1. **Sparse labels** → Model only learns on small subset
2. **Class imbalance** → Model biased toward class 0
3. **100% recall** → Predicts everything as feature
4. **Naive grouping** → Merges all features into one blob
5. **IoU threshold** → No matches (accuracy = 0%)

---

## Attempted Solutions

### ✅ Fix Edge Extraction
- Changed `"face_adjacent_face"` → `"adjacent"`
- Graphs now have proper connectivity
- F1 improved: 79.8% → 80.2% (marginal)

### ❌ Retrain with Edges
- Did improve attention mechanism
- But didn't fix fundamental class bias
- Still predicts 100% as features

### ❌ Instance-Level Validation
- Exposed the grouping problem
- Confirmed 0% accuracy on real task
- Face-level metrics were misleading

---

## What Would Be Required to Make GNN Work

### Short-Term Fixes (1-2 days)
1. **Calibration/Thresholding**
   - Add prediction threshold (e.g., prob > 0.8 for class 0)
   - Reduce false positives
   - Trade recall for precision

2. **Smarter Grouping**
   - Use dihedral angle boundaries
   - Split on concave edges (>180°)
   - Detect feature type transitions

3. **Class Balancing**
   - Weighted loss function
   - Oversample minority class
   - Focal loss for imbalance

### Long-Term Fixes (1-2 weeks)
4. **Hierarchical GNN**
   - Graph pooling to predict instances directly
   - Avoid grouping step entirely
   - DiffPool or SAGPool architecture

5. **Multi-Task Learning**
   - Task 1: Face classification
   - Task 2: Feature boundary detection
   - Task 3: Feature type classification

6. **Better Labels**
   - Label ALL faces (not just features)
   - Explicitly mark feature boundaries
   - Multi-instance annotation

---

## Alternative Approaches

Given the GNN failure, recommend:

### Option A: Classical Geometry + Rules
- Use geometric invariants (dihedral angles, face counts, orientations)
- Decision tree or Random Forest on hand-crafted features
- **Pros**: Interpretable, fast, no training needed
- **Cons**: May not reach 85% accuracy

### Option B: Hybrid Approach
- GNN for face classification (keep 80% F1)
- Geometric rules for grouping boundaries
- Separate classifier for feature types
- **Pros**: Leverages GNN strengths, fixes grouping
- **Cons**: Complex pipeline

### Option C: Instance Segmentation GNN
- PointNet++ or similar architecture
- Directly predict feature instances (not faces)
- End-to-end instance segmentation
- **Pros**: Proper framing of the problem
- **Cons**: Requires architectural overhaul

---

## Lessons Learned

### What Worked
1. **PyTorch Geometric integration** - Clean, efficient
2. **Dataset loading** - MFCAD loader works well
3. **Validation framework** - Exposed hidden problems
4. **Face-level features** - 12D features are informative

### What Didn't Work
1. **Binary face classification** - Wrong level of granularity
2. **BFS grouping** - Too naive for complex geometry
3. **Sparse label training** - Doesn't generalize to dense inference
4. **IoU matching** - Sensitive to grouping errors

### Critical Mistakes
1. **Trusting face-level F1** without instance validation
2. **Not checking graph structure** (0 edges for entire training!)
3. **Assuming grouping would be trivial**
4. **Not addressing class imbalance early**

---

## Recommendations

### Immediate Next Steps
1. **Abandon pure GNN approach** for now
2. **Implement geometric rule-based grouping**:
   - Split on concave edges (>180° dihedral)
   - Use face orientation to detect boundaries
   - Classify groups based on topology patterns

3. **Fallback to proven methods**:
   - Use the 6 rule-based recognizers already implemented
   - Iteratively improve based on MFCAD error analysis
   - Target 75% accuracy (realistic for rules)

### Long-Term Research
If revisiting GNN:
- Reframe as **instance segmentation**, not face classification
- Use **graph pooling** (DiffPool, MinCutPool) to predict instances directly
- Train on **fully labeled** data (label all faces, not just features)
- Use **multi-task loss** (boundary + type + segmentation)

---

## Files Modified/Created

### ML Infrastructure
- `app/ml/__init__.py` - Package initialization
- `app/ml/graph_converter.py` - AAG to PyG conversion (FIXED edge bug)
- `app/ml/mfcad_dataset.py` - PyTorch Geometric dataset
- `app/ml/gnn_model.py` - GAT architecture

### Training
- `scripts/train_gnn.py` - Training loop
- `models/gnn_face_classifier.pt` - Trained model checkpoint (80.2% F1)

### Integration
- `app/recognizers/features/gnn_recognizer.py` - GNN recognizer class (FIXED model path)

### Validation
- `scripts/validate_gnn_recognizer.py` - End-to-end validation script
- `scripts/debug_gnn_predictions.py` - Debug predictions
- `scripts/debug_aag_edges.py` - Debug graph structure

### Reports
- `GNN_IMPLEMENTATION_REPORT.md` - Initial (optimistic) report
- `GNN_FINAL_REPORT.md` - This document (realistic assessment)

---

## Conclusion

The GNN approach **technically achieved 80% face-level F1**, but this metric was **misleading**. The approach **completely failed** at the actual task (0% instance-level accuracy) due to:

1. **Architectural mismatch**: Face classification ≠ instance segmentation
2. **Critical bugs**: 0 edges during training (GAT was broken)
3. **Naive assumptions**: Grouping is NOT trivial
4. **Evaluation disconnect**: Face metrics don't predict instance performance

**Recommendation**: **Do NOT pursue GNN further** without major architectural changes. Recommend returning to geometric rule-based approaches with iterative refinement using MFCAD error analysis.

The 85% accuracy target is achievable, but GNN is the wrong tool for this specific problem framing.

---

**Report Generated**: 2025-12-29
**Author**: Claude (Sonnet 4.5)
**Project**: Palmetto MFCAD Feature Recognition
**Outcome**: GNN approach abandoned after 0% instance-level validation
