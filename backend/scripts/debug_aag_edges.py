"""Debug AAG edge relationships."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.testing.mfcad_loader import MFCADLoader
from app.core.topology.builder import AAGBuilder
from app.core.topology.graph import TopologyType
from app.core.topology.attributes import SurfaceType
from collections import Counter

# Load one test model
loader = MFCADLoader("/tmp/MFCAD/dataset/step")
test_ids = loader.get_all_model_ids()[:1000]
model_id = test_ids[700]

print(f"Loading model: {model_id}")
model = loader.load_model(model_id)

# Build AAG
aag = AAGBuilder(model.shape).build()

# Count node types
node_types = Counter(n.topology_type for n in aag.nodes.values())
print(f"\nNode types:")
for ntype, count in node_types.items():
    print(f"  {ntype}: {count}")

# Count planar faces
planar_faces = [n for n in aag.get_nodes_by_type(TopologyType.FACE)
                if n.attributes.get('surface_type') == SurfaceType.PLANE]
print(f"\nPlanar faces: {len(planar_faces)}")

# Check edge relationships
edge_types = Counter(e.relationship.value for e in aag.edges.values())
print(f"\nEdge relationship types ({len(aag.edges)} total):")
for etype, count in sorted(edge_types.items()):
    print(f"  {etype}: {count}")

# Check face-to-face edges specifically
face_face_edges = [e for e in aag.edges.values() if e.relationship.value == "face_adjacent_face"]
print(f"\nFace-adjacent-face edges: {len(face_face_edges)}")

if face_face_edges:
    print("Sample edges:")
    for e in face_face_edges[:5]:
        print(f"  {e.source} -> {e.target}")
else:
    print("\n⚠️  NO FACE-ADJACENT-FACE EDGES FOUND!")
    print("Checking what face-related edges exist:")
    face_edges = [e for e in aag.edges.values() if 'face' in e.source.lower() and 'face' in e.target.lower()]
    print(f"  Face-related edges: {len(face_edges)}")
    if face_edges:
        face_edge_types = Counter(e.relationship.value for e in face_edges)
        for etype, count in face_edge_types.items():
            print(f"    {etype}: {count}")
