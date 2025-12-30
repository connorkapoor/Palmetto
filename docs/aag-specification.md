# Attributed Adjacency Graph (AAG) Specification

## Overview

The Attributed Adjacency Graph (AAG) is the core data structure used in Palmetto for representing CAD model topology and geometry. It provides a unified representation that enables graph-based pattern matching for feature recognition.

## Motivation

Traditional CAD representations (B-Rep) store topology implicitly in the geometric kernel. The AAG makes topology explicit as a graph, enabling:

- **Graph-based algorithms**: Pattern matching, isomorphism detection, traversal
- **Attribute attachment**: Geometric properties stored directly on nodes/edges
- **Relationship reasoning**: Query adjacent faces, bounding edges, coplanar faces
- **Machine learning**: Graph neural networks can operate on AAG representations

## Graph Structure

The AAG is a directed graph with two types of elements:

### Nodes (AAGNode)

Nodes represent topological entities from the B-Rep hierarchy:

- **VERTEX**: 0D topological element (point)
- **EDGE**: 1D topological element (curve)
- **FACE**: 2D topological element (surface)
- **SHELL**: 2.5D topological element (connected set of faces)
- **SOLID**: 3D topological element (complete volume)

#### Node Structure

```python
@dataclass
class AAGNode:
    node_id: str                    # Unique identifier (UUID or hash)
    topology_type: TopologyType     # VERTEX, EDGE, FACE, SHELL, SOLID
    occt_entity: Any                # pythonOCC object (TopoDS_Vertex, etc.)
    attributes: Dict[str, Any]      # Geometric properties
```

#### Node Attributes by Type

**VERTEX Attributes:**
```python
{
    'point': [x, y, z],                    # 3D coordinates
    'convexity': 'convex'|'concave'|'flat', # Local convexity
    'adjacent_edge_count': int              # Number of edges meeting at vertex
}
```

**EDGE Attributes:**
```python
{
    'curve_type': str,          # 'line', 'circle', 'ellipse', 'bspline', etc.
    'length': float,             # Curve length
    'start_point': [x, y, z],    # Start vertex coordinates
    'end_point': [x, y, z],      # End vertex coordinates
    'tangent': [dx, dy, dz],     # Tangent vector at midpoint
    'center': [x, y, z],         # For circular arcs
    'radius': float,             # For circular arcs
    'is_closed': bool,           # True for full circles/ellipses
    'is_degenerate': bool        # True for zero-length edges
}
```

**FACE Attributes:**
```python
{
    'surface_type': str,         # 'plane', 'cylinder', 'cone', 'sphere', 'torus', 'bspline'
    'area': float,               # Surface area
    'normal': [nx, ny, nz],      # Normal vector (for planar faces)
    'center_of_mass': [x, y, z], # Centroid
    'curvature': float,          # Gaussian curvature (average)
    'radius': float,             # For cylindrical/spherical/toroidal faces
    'axis': [dx, dy, dz],        # For cylindrical/conical faces
    'apex': [x, y, z],           # For conical faces
    'major_radius': float,       # For toroidal faces
    'minor_radius': float,       # For toroidal faces
    'u_period': float,           # U parametric period (if periodic)
    'v_period': float,           # V parametric period (if periodic)
    'is_planar': bool,           # True for flat faces
    'edge_count': int,           # Number of bounding edges
    'orientation': 'forward'|'reversed'  # Face orientation
}
```

**SHELL Attributes:**
```python
{
    'face_count': int,           # Number of faces in shell
    'is_closed': bool,           # True if shell is watertight
    'volume': float,             # Enclosed volume (if closed)
    'surface_area': float        # Total surface area
}
```

**SOLID Attributes:**
```python
{
    'volume': float,             # Total volume
    'surface_area': float,       # Total surface area
    'shell_count': int,          # Number of shells (usually 1)
    'bounding_box': {            # Axis-aligned bounding box
        'min': [x, y, z],
        'max': [x, y, z]
    }
}
```

### Edges (AAGEdge)

Edges represent relationships between topological entities:

```python
@dataclass
class AAGEdge:
    edge_id: str                  # Unique identifier
    source: str                   # Source node ID
    target: str                   # Target node ID
    relationship: RelationType    # Type of relationship
    attributes: Dict[str, Any]    # Relationship-specific data
```

#### Relationship Types

**BOUNDS / BOUNDED_BY:**
Hierarchical containment in B-Rep topology:
- Edge BOUNDS Vertex (edge connects two vertices)
- Face BOUNDS Edge (face has edges as boundaries)
- Shell BOUNDS Face (shell contains faces)
- Solid BOUNDS Shell (solid contains shells)

Direction: BOUNDS goes from higher dimension to lower, BOUNDED_BY is reverse.

```python
# Example: Face with 4 edges
face --BOUNDS--> edge1
face --BOUNDS--> edge2
face --BOUNDS--> edge3
face --BOUNDS--> edge4

# Reverse direction
edge1 --BOUNDED_BY--> face
```

**ADJACENT:**
Topological adjacency:
- Face ADJACENT Face (faces share an edge)
- Edge ADJACENT Edge (edges share a vertex)
- Vertex ADJACENT Vertex (connected by edge)

Attributes:
```python
{
    'shared_entity': str,        # ID of shared edge/vertex
    'dihedral_angle': float,     # For face-face adjacency (degrees)
    'angle_type': str            # 'convex', 'concave', 'tangent', 'sharp'
}
```

**COPLANAR:**
Geometric relationship between planar faces:
- Face COPLANAR Face (faces lie in same plane)

Attributes:
```python
{
    'tolerance': float,          # Distance tolerance used
    'normal_deviation': float    # Angle between normals (degrees)
}
```

**TANGENT:**
Geometric relationship for smooth blends:
- Face TANGENT Face (faces meet smoothly, e.g., fillet)

Attributes:
```python
{
    'shared_edge': str,          # ID of shared edge
    'continuity': str            # 'G0', 'G1', 'G2' (geometric continuity)
}
```

**PARALLEL:**
Geometric relationship:
- Face PARALLEL Face (normals are parallel)

**PERPENDICULAR:**
Geometric relationship:
- Face PERPENDICULAR Face (normals are perpendicular)

### Graph Container

```python
class AttributedAdjacencyGraph:
    def __init__(self):
        self.nodes: Dict[str, AAGNode] = {}                    # node_id -> AAGNode
        self.edges: Dict[str, AAGEdge] = {}                    # edge_id -> AAGEdge
        self._adjacency_list: Dict[str, List[str]] = {}        # node_id -> [edge_ids]
```

## Construction Algorithm

The AAG is built from a `TopoDS_Shape` (pythonOCC B-Rep representation) in three phases:

### Phase 1: Topology Extraction

Use `TopExp_Explorer` to traverse the B-Rep hierarchy:

```python
def _extract_topology(shape: TopoDS_Shape) -> List[AAGNode]:
    nodes = []

    # Extract vertices
    vertex_explorer = TopExp_Explorer(shape, TopAbs_VERTEX)
    while vertex_explorer.More():
        vertex = topods.Vertex(vertex_explorer.Current())
        node = AAGNode(
            node_id=compute_hash(vertex),
            topology_type=TopologyType.VERTEX,
            occt_entity=vertex,
            attributes={}
        )
        nodes.append(node)
        vertex_explorer.Next()

    # Repeat for EDGE, FACE, SHELL, SOLID
    # ...

    return nodes
```

**Hashing**: Use geometry-based hashing to generate consistent node IDs:
```python
def compute_hash(entity: TopoDS_Shape) -> str:
    # For vertices: hash coordinates
    # For edges: hash curve type + endpoints
    # For faces: hash surface type + bounding edges
    return hashlib.sha256(geometry_bytes).hexdigest()[:16]
```

### Phase 2: Attribute Computation

For each node, compute geometric attributes using pythonOCC analysis tools:

```python
def compute_face_attributes(face: TopoDS_Face) -> Dict[str, Any]:
    # Surface type
    surface = BRep_Tool.Surface_s(face)
    surface_type = classify_surface(surface)

    # Area
    props = GProp_GProps()
    brepgprop.SurfaceProperties_s(face, props)
    area = props.Mass()

    # Normal (for planar faces)
    if surface_type == 'plane':
        plane = geom_Plane.DownCast(surface)
        axis = plane.Axis()
        normal = [axis.Direction().X(), axis.Direction().Y(), axis.Direction().Z()]

    # Curvature analysis
    # ...

    return {
        'surface_type': surface_type,
        'area': area,
        'normal': normal,
        # ... other attributes
    }
```

**Surface Classification:**
```python
def classify_surface(surface: Geom_Surface) -> str:
    if geom_Plane.DownCast(surface):
        return 'plane'
    elif geom_CylindricalSurface.DownCast(surface):
        return 'cylinder'
    elif geom_ConicalSurface.DownCast(surface):
        return 'cone'
    elif geom_SphericalSurface.DownCast(surface):
        return 'sphere'
    elif geom_ToroidalSurface.DownCast(surface):
        return 'torus'
    else:
        return 'bspline'  # BSpline or other parametric surface
```

### Phase 3: Relationship Establishment

Build edges representing topological and geometric relationships:

```python
def establish_adjacency_relationships(graph: AAG):
    # Face-Face adjacency via shared edges
    edge_to_faces = defaultdict(list)

    for face_node in graph.get_nodes_by_type(TopologyType.FACE):
        face = face_node.occt_entity
        edge_explorer = TopExp_Explorer(face, TopAbs_EDGE)

        while edge_explorer.More():
            edge = topods.Edge(edge_explorer.Current())
            edge_id = compute_hash(edge)
            edge_to_faces[edge_id].append(face_node.node_id)
            edge_explorer.Next()

    # Create adjacency edges for faces sharing an edge
    for edge_id, face_ids in edge_to_faces.items():
        if len(face_ids) == 2:
            face1_id, face2_id = face_ids
            face1 = graph.nodes[face1_id]
            face2 = graph.nodes[face2_id]

            # Compute dihedral angle
            dihedral = compute_dihedral_angle(face1.occt_entity, face2.occt_entity)
            angle_type = classify_angle(dihedral)

            # Create bidirectional adjacency
            graph.add_edge(AAGEdge(
                source=face1_id,
                target=face2_id,
                relationship=RelationType.ADJACENT,
                attributes={
                    'shared_edge': edge_id,
                    'dihedral_angle': dihedral,
                    'angle_type': angle_type
                }
            ))
```

**Dihedral Angle Computation:**
```python
def compute_dihedral_angle(face1: TopoDS_Face, face2: TopoDS_Face) -> float:
    # Get normals at shared edge midpoint
    normal1 = get_normal_at_edge(face1, shared_edge)
    normal2 = get_normal_at_edge(face2, shared_edge)

    # Compute angle
    dot_product = normal1.Dot(normal2)
    angle = math.degrees(math.acos(np.clip(dot_product, -1.0, 1.0)))

    # Adjust for orientation
    # Convex: > 180°, Concave: < 180°
    return angle
```

## Query Interface

The AAG provides methods for graph traversal and analysis:

### Neighbor Queries

```python
# Get all neighbors
neighbors = graph.get_neighbors(node_id)

# Get neighbors of specific type
adjacent_faces = graph.get_neighbors(node_id, RelationType.ADJACENT)

# Get neighbors filtered by attribute
cylindrical_neighbors = [
    n for n in graph.get_neighbors(face_id)
    if n.attributes.get('surface_type') == 'cylinder'
]
```

### Topological Queries

```python
# Get faces adjacent to an edge
faces = graph.get_faces_adjacent_to_edge(edge_id)

# Get edges bounding a face
edges = graph.get_edges_bounding_face(face_id)

# Get all faces in the model
all_faces = graph.get_nodes_by_type(TopologyType.FACE)
```

### Pattern Matching

```python
# Define pattern
pattern = GraphPattern()
pattern.add_node_constraint('cylinder', {
    'topology_type': 'face',
    'surface_type': 'cylinder'
})
pattern.add_node_constraint('cap', {
    'topology_type': 'face',
    'surface_type': 'plane'
})
pattern.add_edge_constraint('cylinder', 'cap', RelationType.ADJACENT)

# Find matches
matches = graph.find_subgraph(pattern)

for match in matches:
    cylinder = match.node_mapping['cylinder']
    cap = match.node_mapping['cap']
    # Process matched pattern
```

## Example: Hole Detection Using AAG

```python
def detect_hole(graph: AAG, min_diameter: float, max_diameter: float):
    """Detect cylindrical holes using AAG queries."""

    # Step 1: Find cylindrical faces in diameter range
    candidate_faces = [
        node for node in graph.get_nodes_by_type(TopologyType.FACE)
        if (node.attributes.get('surface_type') == 'cylinder' and
            min_diameter/2 <= node.attributes.get('radius', 0) <= max_diameter/2)
    ]

    holes = []

    for cyl_face in candidate_faces:
        # Step 2: Check if cylinder is subtractive (concave dihedral angles)
        adjacent_faces = graph.get_neighbors(cyl_face.node_id, RelationType.ADJACENT)

        concave_count = 0
        for adj_face in adjacent_faces:
            # Get edge connecting them
            edge = graph.get_edge_between(cyl_face.node_id, adj_face.node_id)
            dihedral = edge.attributes.get('dihedral_angle', 180)

            if dihedral < 175:  # Concave
                concave_count += 1

        # If mostly concave, it's a hole
        if concave_count >= len(adjacent_faces) * 0.6:
            # Step 3: Classify hole type
            bounding_edges = graph.get_edges_bounding_face(cyl_face.node_id)
            circular_edges = [
                e for e in bounding_edges
                if e.attributes.get('curve_type') == 'circle'
            ]

            if len(circular_edges) == 2:
                # Simple hole with two circular edges
                holes.append({
                    'type': 'simple_hole',
                    'diameter': cyl_face.attributes['radius'] * 2,
                    'face_id': cyl_face.node_id
                })

    return holes
```

## Storage and Serialization

### In-Memory Representation

The AAG is stored in-memory using Python dictionaries for fast access:

```python
{
    'nodes': {
        'face_abc123': AAGNode(...),
        'edge_def456': AAGNode(...),
        # ...
    },
    'edges': {
        'rel_xyz789': AAGEdge(...),
        # ...
    }
}
```

### Serialization (Future)

For persistence, the AAG can be serialized to formats like:

**JSON:**
```json
{
    "nodes": [
        {
            "node_id": "face_abc123",
            "topology_type": "face",
            "attributes": {
                "surface_type": "cylinder",
                "radius": 5.0,
                "area": 157.08
            }
        }
    ],
    "edges": [
        {
            "edge_id": "rel_xyz789",
            "source": "face_abc123",
            "target": "face_def456",
            "relationship": "adjacent",
            "attributes": {
                "dihedral_angle": 165.0,
                "angle_type": "concave"
            }
        }
    ]
}
```

**Graph Databases (Neo4j, NetworkX):**
```python
import networkx as nx

def to_networkx(aag: AAG) -> nx.DiGraph:
    G = nx.DiGraph()

    for node in aag.nodes.values():
        G.add_node(node.node_id, **node.attributes, type=node.topology_type)

    for edge in aag.edges.values():
        G.add_edge(edge.source, edge.target, **edge.attributes, rel=edge.relationship)

    return G
```

## Performance Considerations

### Indexing

For large models (>10,000 faces), create spatial indices:

```python
from rtree import index

class AAGWithSpatialIndex(AAG):
    def __init__(self):
        super().__init__()
        self.spatial_index = index.Index()

    def add_node(self, node: AAGNode):
        super().add_node(node)

        if node.topology_type == TopologyType.FACE:
            bbox = node.attributes.get('bounding_box')
            if bbox:
                # Insert into R-tree
                self.spatial_index.insert(
                    id=hash(node.node_id),
                    coordinates=(bbox['min'] + bbox['max']),
                    obj=node.node_id
                )

    def query_region(self, bbox) -> List[AAGNode]:
        """Find faces in bounding box region."""
        hits = self.spatial_index.intersection(bbox)
        return [self.nodes[node_id] for node_id in hits]
```

### Caching

Cache expensive computations:

```python
from functools import lru_cache

class AAG:
    @lru_cache(maxsize=1000)
    def get_neighbors(self, node_id: str, rel_type=None):
        # Cached neighbor queries
        # ...
```

## Comparison with B-Rep

| Aspect | B-Rep (TopoDS_Shape) | AAG |
|--------|----------------------|-----|
| Representation | Implicit topology | Explicit graph |
| Queries | Iterative exploration | Direct graph queries |
| Attributes | Computed on-demand | Pre-computed and stored |
| Relationships | Implicit in structure | Explicit edges |
| Pattern Matching | Difficult | Natural (subgraph isomorphism) |
| ML Integration | Requires conversion | Direct use in GNNs |

## Extensions

### Adding Custom Attributes

```python
# Add manufacturing-specific attributes
for face_node in graph.get_nodes_by_type(TopologyType.FACE):
    face_node.attributes['machinability_score'] = compute_machinability(face_node)
    face_node.attributes['surface_finish'] = estimate_finish(face_node)
```

### Adding Custom Relationships

```python
# Add manufacturing relationships
for face1, face2 in face_pairs:
    if requires_tool_change(face1, face2):
        graph.add_edge(AAGEdge(
            source=face1.node_id,
            target=face2.node_id,
            relationship=RelationType.REQUIRES_TOOL_CHANGE,
            attributes={'tool_change_time': 30}  # seconds
        ))
```

## References

- Analysis Situs Framework: https://analysissitus.org/features/features_feature-recognition-framework.html
- OpenCASCADE Documentation: https://dev.opencascade.org/doc/overview/html/
- Graph-based Feature Recognition Papers:
  - Verma & Rajotia (2010): "A review of machining feature recognition methodologies"
  - Sunil & Pande (2008): "Automatic recognition of features from freeform surface CAD models"

## Summary

The AAG provides a powerful abstraction for CAD analysis:

1. **Unified representation**: Topology + geometry in one structure
2. **Explicit relationships**: Easy to query adjacency, tangency, etc.
3. **Graph algorithms**: Pattern matching, traversal, clustering
4. **Extensible**: Add attributes and relationships as needed
5. **Feature recognition**: Natural representation for template matching

The AAG is the foundation that makes Palmetto's plugin-based recognizer architecture possible.
