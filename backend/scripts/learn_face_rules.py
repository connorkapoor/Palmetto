#!/usr/bin/env python3
"""
Learn face classification rules from labeled MFCAD data.

Analyze geometric properties of faces labeled as features vs stock
to discover discriminative rules.
"""

import sys
import logging
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.testing.mfcad_loader import MFCADLoader, FEAT_NAMES
from app.core.topology.builder import AAGBuilder
from app.core.topology.graph import TopologyType
from app.core.topology.attributes import SurfaceType

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


def analyze_face(face_node, graph):
    """Extract features from a face."""

    area = face_node.attributes.get('area', 0)
    normal = face_node.attributes.get('normal')

    if not normal or area == 0:
        return None

    # Analyze dihedral angles
    adjacent_faces = []
    for rel in graph.relationships:
        if rel.relation_type.value == "face_adjacent_face":
            if rel.source_id == face_node.node_id:
                adjacent_faces.append(rel.target_id)
            elif rel.target_id == face_node.node_id:
                adjacent_faces.append(rel.source_id)

    dihedrals = []
    for adj_id in adjacent_faces:
        adj_node = graph.get_node(adj_id)
        if adj_node and adj_node.attributes.get('surface_type') == SurfaceType.PLANE:
            dihedral = graph.get_cached_dihedral_angle(face_node.node_id, adj_id)
            if dihedral is None:
                dihedral = graph.get_cached_dihedral_angle(adj_id, face_node.node_id)
            if dihedral:
                dihedrals.append(dihedral)

    if not dihedrals:
        return None

    num_concave = sum(1 for d in dihedrals if d > 200.0)
    num_convex = sum(1 for d in dihedrals if d < 160.0)

    return {
        'area': area,
        'normal_z': abs(normal.Z()),
        'num_dihedrals': len(dihedrals),
        'min_dihedral': min(dihedrals),
        'max_dihedral': max(dihedrals),
        'avg_dihedral': sum(dihedrals) / len(dihedrals),
        'num_concave': num_concave,
        'num_convex': num_convex
    }


def main():
    """Analyze face properties from labeled data."""

    loader = MFCADLoader("/tmp/MFCAD/dataset/step")
    model_ids = loader.get_all_model_ids()[:20]

    feature_props = []
    stock_props = []

    print("Analyzing face properties from labeled data...")
    print("=" * 80)

    for model_id in model_ids:
        try:
            model = loader.load_model(model_id)

            # Build AAG
            aag_builder = AAGBuilder(model.shape)
            graph = aag_builder.build()

            # Analyze each planar face
            for node in graph.get_nodes_by_type(TopologyType.FACE):
                if node.attributes.get('surface_type') != SurfaceType.PLANE:
                    continue

                if not node.node_id.startswith("face_"):
                    continue

                try:
                    face_id = int(node.node_id.split("_")[1])
                except:
                    continue

                props = analyze_face(node, graph)
                if not props:
                    continue

                # Check if feature or stock
                label = model.face_labels[face_id]
                if label == 15:  # Stock
                    stock_props.append(props)
                else:  # Feature
                    feature_props.append(props)

        except Exception as e:
            print(f"Failed on {model_id}: {e}")
            continue

    print(f"\nAnalyzed {len(feature_props)} feature faces and {len(stock_props)} stock faces\n")

    # Compute statistics
    def stats(values):
        if not values:
            return "N/A"
        return f"min={min(values):.1f}, max={max(values):.1f}, avg={sum(values)/len(values):.1f}, median={sorted(values)[len(values)//2]:.1f}"

    print("=" * 80)
    print("FEATURE FACES (labeled as slots, pockets, etc.):")
    print("=" * 80)
    print(f"Area: {stats([p['area'] for p in feature_props])}")
    print(f"Avg dihedral: {stats([p['avg_dihedral'] for p in feature_props])}")
    print(f"Num concave edges: {stats([p['num_concave'] for p in feature_props])}")
    print(f"Num convex edges: {stats([p['num_convex'] for p in feature_props])}")

    print("\n" + "=" * 80)
    print("STOCK FACES (labeled as stock/base material):")
    print("=" * 80)
    print(f"Area: {stats([p['area'] for p in stock_props])}")
    print(f"Avg dihedral: {stats([p['avg_dihedral'] for p in stock_props])}")
    print(f"Num concave edges: {stats([p['num_concave'] for p in stock_props])}")
    print(f"Num convex edges: {stats([p['num_convex'] for p in stock_props])}")

    # Find discriminative thresholds
    print("\n" + "=" * 80)
    print("DISCRIMINATIVE ANALYSIS:")
    print("=" * 80)

    # Concave edges
    feature_concave = [p['num_concave'] for p in feature_props]
    stock_concave = [p['num_concave'] for p in stock_props]

    print(f"\nConcave edges (>200°):")
    print(f"  Features: {sum(feature_concave)/len(feature_concave):.2f} avg")
    print(f"  Stock: {sum(stock_concave)/len(stock_concave):.2f} avg")

    # Area
    feature_areas = [p['area'] for p in feature_props]
    stock_areas = [p['area'] for p in stock_props]

    print(f"\nArea:")
    print(f"  Features: {sum(feature_areas)/len(feature_areas):.1f} avg")
    print(f"  Stock: {sum(stock_areas)/len(stock_areas):.1f} avg")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
