# Adding New Feature Recognizers

This guide explains how to implement custom feature recognizers in the Palmetto framework.

## Overview

Palmetto uses a plugin-based architecture where recognizers are automatically registered via decorators. Each recognizer operates on the Attributed Adjacency Graph (AAG) representation of the CAD model.

## Basic Structure

Every recognizer must:
1. Inherit from `BaseRecognizer`
2. Use the `@register_recognizer` decorator
3. Implement required abstract methods
4. Return `RecognizedFeature` objects

## Step-by-Step Guide

### 1. Create a New Recognizer File

Create a new file in `backend/app/recognizers/features/`:

```python
# backend/app/recognizers/features/my_feature.py

from typing import List, Optional
from app.recognizers.base import (
    BaseRecognizer,
    RecognizedFeature,
    FeatureType,
    register_recognizer
)
from app.core.topology.graph import AttributedAdjacencyGraph, AAGNode
```

### 2. Define Your Recognizer Class

```python
@register_recognizer
class MyFeatureRecognizer(BaseRecognizer):
    """
    Recognizes [describe your feature here].

    Recognition algorithm:
    1. [Step 1]
    2. [Step 2]
    3. [Step 3]
    """

    def get_name(self) -> str:
        """Unique identifier for this recognizer."""
        return "my_feature_detector"

    def get_description(self) -> str:
        """Human-readable description for natural language interface."""
        return "Detects [feature description] in CAD models"

    def get_feature_types(self) -> List[FeatureType]:
        """List of feature types this recognizer can detect."""
        return [FeatureType.MY_FEATURE]  # Add to FeatureType enum first

    def recognize(self, **kwargs) -> List[RecognizedFeature]:
        """
        Main recognition logic.

        Args:
            **kwargs: Recognition parameters (e.g., min_size, max_size)

        Returns:
            List of RecognizedFeature objects
        """
        features = []

        # Your recognition logic here
        # See examples below

        return features
```

### 3. Add Feature Type to Enum

Before implementing the recognizer, add your feature type to the enum in `backend/app/recognizers/base.py`:

```python
class FeatureType(Enum):
    # Existing types...
    MY_FEATURE = "my_feature"
```

### 4. Import in Main App

Add your recognizer to the imports in `backend/app/main.py`:

```python
from app.recognizers.features import holes, shafts, fillets, cavities, my_feature  # noqa
```

This ensures the `@register_recognizer` decorator runs and registers your recognizer.

## Complete Examples

### Example 1: Simple Hole Recognizer

```python
from typing import List
from app.recognizers.base import BaseRecognizer, RecognizedFeature, FeatureType, register_recognizer
from app.core.topology.graph import AttributedAdjacencyGraph, SurfaceType

@register_recognizer
class SimpleHoleRecognizer(BaseRecognizer):
    def get_name(self) -> str:
        return "simple_hole_detector"

    def get_description(self) -> str:
        return "Detects simple drilled holes (cylindrical cavities)"

    def get_feature_types(self) -> List[FeatureType]:
        return [FeatureType.HOLE_SIMPLE]

    def recognize(self, min_diameter: float = 0.0, max_diameter: float = float('inf')) -> List[RecognizedFeature]:
        features = []

        # Step 1: Find cylindrical faces in diameter range
        cylindrical_faces = self._find_cylindrical_faces(
            min_radius=min_diameter / 2,
            max_radius=max_diameter / 2
        )

        # Step 2: Check each cylinder for hole characteristics
        for cyl_face in cylindrical_faces:
            # Get adjacent faces
            neighbors = self.graph.get_neighbors(cyl_face.node_id)

            # Check if this cylinder is subtractive (hole) or additive (shaft)
            concave_count = 0
            for neighbor in neighbors:
                if neighbor.topology_type.value == 'face':
                    # Check dihedral angle
                    angle = self._get_dihedral_angle(cyl_face, neighbor)
                    if angle and angle < 175:  # Concave
                        concave_count += 1

            # If mostly concave, it's likely a hole
            if concave_count >= len(neighbors) * 0.5:
                # Extract properties
                radius = cyl_face.attributes.get('radius', 0.0)
                axis = cyl_face.attributes.get('axis', [0, 0, 1])

                # Calculate depth (simplified)
                depth = self._calculate_cylinder_depth(cyl_face)

                # Create feature
                feature = RecognizedFeature(
                    feature_type=FeatureType.HOLE_SIMPLE,
                    confidence=0.9,
                    face_ids=[cyl_face.node_id],
                    properties={
                        'diameter': radius * 2,
                        'radius': radius,
                        'depth': depth,
                        'axis': axis,
                        'is_through': depth > 100  # Heuristic
                    },
                    metadata={
                        'recognizer': self.get_name(),
                        'algorithm_version': '1.0'
                    }
                )
                features.append(feature)

        return features

    def _calculate_cylinder_depth(self, cyl_face: AAGNode) -> float:
        """Calculate cylinder depth from bounding edges."""
        edges = self.graph.get_edges_bounding_face(cyl_face.node_id)

        # Find circular edges
        circular_edges = [
            e for e in edges
            if e.attributes.get('curve_type') == 'circle'
        ]

        if len(circular_edges) >= 2:
            # Distance between circle centers
            center1 = circular_edges[0].attributes.get('center', [0, 0, 0])
            center2 = circular_edges[1].attributes.get('center', [0, 0, 0])

            import numpy as np
            return float(np.linalg.norm(np.array(center1) - np.array(center2)))

        return 0.0
```

### Example 2: Boss Recognizer (Protruding Cylinder)

```python
@register_recognizer
class BossRecognizer(BaseRecognizer):
    """Detects boss features (protruding cylinders)."""

    def get_name(self) -> str:
        return "boss_detector"

    def get_description(self) -> str:
        return "Detects cylindrical bosses and protrusions"

    def get_feature_types(self) -> List[FeatureType]:
        return [FeatureType.BOSS]  # Add to enum first

    def recognize(self, min_diameter: float = 0.0, max_diameter: float = float('inf')) -> List[RecognizedFeature]:
        features = []

        # Find cylindrical faces
        cylindrical_faces = self._find_cylindrical_faces(
            min_radius=min_diameter / 2,
            max_radius=max_diameter / 2
        )

        for cyl_face in cylindrical_faces:
            # Check if additive (convex angles)
            if self._is_additive_cylinder(cyl_face):
                # Check if it has a planar top
                top_face = self._find_planar_cap(cyl_face)

                if top_face:
                    radius = cyl_face.attributes.get('radius', 0.0)
                    height = self._calculate_cylinder_depth(cyl_face)

                    feature = RecognizedFeature(
                        feature_type=FeatureType.BOSS,
                        confidence=0.85,
                        face_ids=[cyl_face.node_id, top_face.node_id],
                        properties={
                            'diameter': radius * 2,
                            'height': height,
                            'has_top': True
                        }
                    )
                    features.append(feature)

        return features

    def _is_additive_cylinder(self, cyl_face: AAGNode) -> bool:
        """Check if cylinder is protruding (convex angles)."""
        neighbors = self.graph.get_neighbors(cyl_face.node_id)
        convex_count = 0

        for neighbor in neighbors:
            if neighbor.topology_type.value == 'face':
                angle = self._get_dihedral_angle(cyl_face, neighbor)
                if angle and angle > 185:  # Convex
                    convex_count += 1

        return convex_count >= len(neighbors) * 0.5

    def _find_planar_cap(self, cyl_face: AAGNode) -> Optional[AAGNode]:
        """Find planar face capping the cylinder."""
        neighbors = self.graph.get_neighbors(cyl_face.node_id)

        for neighbor in neighbors:
            if (neighbor.topology_type.value == 'face' and
                neighbor.attributes.get('surface_type') == 'plane'):
                # Check if roughly perpendicular to cylinder axis
                return neighbor

        return None
```

### Example 3: Pattern-Based Recognizer

```python
from app.core.topology.graph import GraphPattern

@register_recognizer
class RibRecognizer(BaseRecognizer):
    """Detects rib features using graph pattern matching."""

    def get_name(self) -> str:
        return "rib_detector"

    def get_description(self) -> str:
        return "Detects thin-walled rib features"

    def get_feature_types(self) -> List[FeatureType]:
        return [FeatureType.RIB]

    def recognize(self, max_thickness: float = 5.0) -> List[RecognizedFeature]:
        features = []

        # Define graph pattern for rib:
        # Two parallel planar faces connected by thin walls
        pattern = GraphPattern()

        # Node constraints
        pattern.add_node_constraint('face1', {
            'topology_type': 'face',
            'surface_type': 'plane'
        })
        pattern.add_node_constraint('face2', {
            'topology_type': 'face',
            'surface_type': 'plane'
        })
        pattern.add_node_constraint('wall', {
            'topology_type': 'face',
            'surface_type': 'plane'
        })

        # Edge constraints: faces are parallel
        pattern.add_edge_constraint('face1', 'face2', 'parallel')
        pattern.add_edge_constraint('face1', 'wall', 'adjacent')
        pattern.add_edge_constraint('face2', 'wall', 'adjacent')

        # Find matches
        matches = self.graph.find_subgraph(pattern)

        for match in matches:
            face1 = match.node_mapping['face1']
            face2 = match.node_mapping['face2']
            wall = match.node_mapping['wall']

            # Check thickness
            thickness = self._calculate_distance(face1, face2)

            if thickness <= max_thickness:
                feature = RecognizedFeature(
                    feature_type=FeatureType.RIB,
                    confidence=0.8,
                    face_ids=[face1.node_id, face2.node_id, wall.node_id],
                    properties={
                        'thickness': thickness,
                        'length': self._calculate_face_length(wall),
                        'height': self._calculate_face_height(wall)
                    }
                )
                features.append(feature)

        return features
```

## Utility Methods

The `BaseRecognizer` class provides several utility methods:

### Finding Faces by Type

```python
# Find cylindrical faces in radius range
cylindrical_faces = self._find_cylindrical_faces(min_radius=5.0, max_radius=20.0)

# Find all planar faces
planar_faces = self._find_planar_faces()

# Find faces by custom criteria
def custom_filter(node):
    return (node.attributes.get('surface_type') == 'cone' and
            node.attributes.get('area', 0) > 100)

conical_faces = [n for n in self.graph.nodes.values()
                 if n.topology_type.value == 'face' and custom_filter(n)]
```

### Analyzing Relationships

```python
# Get neighbors
neighbors = self.graph.get_neighbors(face.node_id)

# Get adjacent faces only
adjacent_faces = self.graph.get_neighbors(face.node_id, RelationType.ADJACENT)

# Get faces adjacent to an edge
edge_faces = self.graph.get_faces_adjacent_to_edge(edge.node_id)

# Get edges bounding a face
bounding_edges = self.graph.get_edges_bounding_face(face.node_id)
```

### Computing Geometry

```python
# Dihedral angle between faces
angle = self._get_dihedral_angle(face1, face2)

# Check if faces are coplanar
if self._are_coplanar(face1, face2):
    # ...

# Distance between faces (custom implementation)
distance = self._calculate_distance(face1, face2)
```

## Natural Language Integration

Your recognizer is automatically available to the natural language interface. The Claude API uses the `get_name()` and `get_description()` to map commands to recognizers.

Example commands that would invoke your recognizer:

```
"find all my_feature"
"detect my_feature larger than 10mm"
"show me my_feature in this model"
```

## Testing Your Recognizer

Create unit tests in `backend/tests/unit/test_recognizers.py`:

```python
import pytest
from app.recognizers.features.my_feature import MyFeatureRecognizer
from app.core.cad_loader import CADLoader
from app.core.topology.builder import AAGBuilder

def test_my_feature_recognizer():
    # Load test CAD file
    shape = CADLoader.load('tests/fixtures/test_model.step')

    # Build AAG
    builder = AAGBuilder(shape)
    graph = builder.build()

    # Run recognizer
    recognizer = MyFeatureRecognizer(graph)
    features = recognizer.recognize()

    # Assertions
    assert len(features) > 0
    assert features[0].feature_type == FeatureType.MY_FEATURE
    assert features[0].confidence > 0.5
```

## Best Practices

1. **Confidence Scoring**: Use confidence values (0.0-1.0) to indicate recognition certainty
   - 0.9-1.0: Very certain (exact geometric match)
   - 0.7-0.9: Confident (matches most criteria)
   - 0.5-0.7: Uncertain (partial match)
   - Below 0.5: Consider not returning the feature

2. **Property Extraction**: Include all relevant geometric properties:
   - Dimensions (diameter, depth, radius, length, etc.)
   - Position (center, axis, normal)
   - Topology (face count, edge count)
   - Material/manufacturing info if applicable

3. **Face IDs**: Always include all relevant face_ids for proper highlighting

4. **Error Handling**: Wrap recognition logic in try-except to prevent crashes:
```python
try:
    # Recognition logic
except Exception as e:
    logger.error(f"Recognition failed: {e}")
    return []
```

5. **Performance**: For large models, use early filtering:
```python
# Filter by bounding box first
faces_in_region = self._filter_by_bounding_box(all_faces, bbox)
# Then run expensive geometric checks
```

6. **Documentation**: Document your algorithm clearly for future maintainers

## Advanced Topics

### Subgraph Matching

For complex features, use graph pattern matching:

```python
pattern = GraphPattern()
pattern.add_node_constraint('central_face', {'surface_type': 'plane'})
pattern.add_node_constraint('wall_1', {'surface_type': 'plane'})
# ... define pattern
matches = self.graph.find_subgraph(pattern)
```

### Multi-Stage Recognition

Break complex recognition into stages:

```python
def recognize(self, **kwargs):
    # Stage 1: Find candidate regions
    candidates = self._find_candidates()

    # Stage 2: Verify geometric constraints
    verified = self._verify_geometry(candidates)

    # Stage 3: Extract properties
    features = self._extract_features(verified)

    return features
```

### Combining Recognizers

Use results from other recognizers:

```python
def recognize(self, **kwargs):
    # Check if holes were already detected
    hole_recognizer = HoleRecognizer(self.graph)
    holes = hole_recognizer.recognize()

    # Find patterns around holes
    features = self._find_patterns_near_holes(holes)
    return features
```

## Troubleshooting

**Problem**: Recognizer not appearing in `/api/recognition/recognizers`
- **Solution**: Ensure `@register_recognizer` decorator is present and file is imported in `main.py`

**Problem**: No features detected
- **Solution**: Print debug info in recognize() to check intermediate results:
```python
print(f"Found {len(cylindrical_faces)} cylindrical faces")
```

**Problem**: Wrong features detected
- **Solution**: Adjust confidence thresholds and geometric tolerances

**Problem**: Performance issues
- **Solution**: Add early filtering, cache expensive computations

## Summary

To add a new recognizer:

1. Create file in `recognizers/features/`
2. Inherit from `BaseRecognizer`
3. Add `@register_recognizer` decorator
4. Implement abstract methods
5. Add feature type to enum
6. Import in `main.py`
7. Test with sample CAD files

Your recognizer is now integrated into the entire pipeline: API endpoints, natural language interface, and 3D visualization!
