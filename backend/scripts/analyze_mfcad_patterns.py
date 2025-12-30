#!/usr/bin/env python3
"""
MFCAD Topology Pattern Analyzer

Loads MFCAD models and analyzes the actual topology patterns of labeled features
to understand how to recognize them.
"""

import sys
import logging
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.testing.mfcad_loader import MFCADLoader
from app.core.topology.builder import AAGBuilder
from app.core.topology.graph import TopologyType
from app.core.topology.attributes import SurfaceType, CurveType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def analyze_feature_topology(model, feature_label_idx):
    """
    Analyze topology of faces with a specific feature label.

    Returns statistics about surface types, edge types, adjacency patterns.
    """
    # Build AAG
    builder = AAGBuilder(model.shape)
    graph = builder.build()

    # Find faces with this label
    feature_face_ids = [
        face_id for face_id in model.face_id_map.keys()
        if model.face_labels[face_id] == feature_label_idx
    ]

    if not feature_face_ids:
        return None

    # Analyze topology patterns
    surface_types = defaultdict(int)
    edge_curve_types = defaultdict(int)
    adjacency_counts = []
    edge_counts = []

    for face_id in feature_face_ids:
        # Find corresponding AAG node (simplified mapping)
        aag_face_id = f"face_{face_id}"
        face_node = graph.get_node(aag_face_id)

        if face_node is None:
            continue

        # Surface type
        surf_type = face_node.attributes.get('surface_type')
        if surf_type:
            surface_types[surf_type.value] += 1

        # Bounding edges
        bounding_edges = graph.get_edges_bounding_face(aag_face_id)
        edge_counts.append(len(bounding_edges))

        for edge in bounding_edges:
            curve_type = edge.attributes.get('curve_type')
            if curve_type:
                edge_curve_types[curve_type.value] += 1

        # Adjacent faces
        adjacent_faces = graph.get_neighbors(aag_face_id)
        adjacency_counts.append(len(adjacent_faces))

    return {
        'num_faces': len(feature_face_ids),
        'surface_types': dict(surface_types),
        'edge_curve_types': dict(edge_curve_types),
        'avg_edges_per_face': sum(edge_counts) / len(edge_counts) if edge_counts else 0,
        'avg_adjacent_faces': sum(adjacency_counts) / len(adjacency_counts) if adjacency_counts else 0
    }


def main():
    """Analyze MFCAD topology patterns."""

    logger.info("=" * 80)
    logger.info("MFCAD TOPOLOGY PATTERN ANALYSIS")
    logger.info("=" * 80)

    loader = MFCADLoader("/tmp/MFCAD/dataset/step")

    # Analyze first 20 models for each feature type
    feature_patterns = defaultdict(list)

    from app.testing.mfcad_loader import FEAT_NAMES

    # Sample models
    sample_ids = loader.get_all_model_ids()[:50]

    logger.info(f"\nAnalyzing {len(sample_ids)} models...\n")

    for model_id in sample_ids:
        try:
            model = loader.load_model(model_id)

            # Analyze each feature type present in this model
            for label_idx in range(15):  # 0-14 (skip stock)
                pattern = analyze_feature_topology(model, label_idx)
                if pattern and pattern['num_faces'] > 0:
                    feature_patterns[FEAT_NAMES[label_idx]].append(pattern)

        except Exception as e:
            logger.error(f"Failed to analyze {model_id}: {e}")
            continue

    # Print results
    logger.info("\n" + "=" * 80)
    logger.info("FEATURE TOPOLOGY PATTERNS")
    logger.info("=" * 80)

    for feature_name in FEAT_NAMES[:-1]:  # Skip stock
        patterns = feature_patterns[feature_name]
        if not patterns:
            continue

        logger.info(f"\n{feature_name.upper()} ({len(patterns)} samples)")
        logger.info("-" * 80)

        # Aggregate statistics
        all_surface_types = defaultdict(int)
        all_edge_types = defaultdict(int)
        total_faces = 0
        avg_edges = []
        avg_adj = []

        for p in patterns:
            total_faces += p['num_faces']
            avg_edges.append(p['avg_edges_per_face'])
            avg_adj.append(p['avg_adjacent_faces'])

            for stype, count in p['surface_types'].items():
                all_surface_types[stype] += count
            for etype, count in p['edge_curve_types'].items():
                all_edge_types[etype] += count

        logger.info(f"Total faces analyzed: {total_faces}")
        logger.info(f"Average edges per face: {sum(avg_edges)/len(avg_edges):.1f}")
        logger.info(f"Average adjacent faces: {sum(avg_adj)/len(avg_adj):.1f}")

        logger.info("\nSurface types:")
        for stype, count in sorted(all_surface_types.items(), key=lambda x: -x[1]):
            pct = 100 * count / total_faces
            logger.info(f"  {stype:20s}: {count:4d} ({pct:5.1f}%)")

        logger.info("\nEdge curve types:")
        total_edges = sum(all_edge_types.values())
        for etype, count in sorted(all_edge_types.items(), key=lambda x: -x[1]):
            pct = 100 * count / total_edges if total_edges > 0 else 0
            logger.info(f"  {etype:20s}: {count:4d} ({pct:5.1f}%)")

    logger.info("\n" + "=" * 80)


if __name__ == "__main__":
    main()
