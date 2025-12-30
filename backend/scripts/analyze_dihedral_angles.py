#!/usr/bin/env python3
"""
Analyze dihedral angles to understand feature boundaries.

Examines which edges have which dihedral angles and how they relate
to ground truth feature boundaries.
"""

import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.testing.mfcad_loader import MFCADLoader, FEAT_NAMES
from app.core.topology.builder import AAGBuilder
from app.core.topology.attributes import SurfaceType
from app.core.topology.graph import TopologyType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def analyze_model_boundaries(model):
    """Analyze edge dihedral angles relative to feature boundaries."""

    # Build AAG
    aag_builder = AAGBuilder(model.shape)
    graph = aag_builder.build()

    # Identify which faces are features vs stock
    feature_faces = set()
    stock_faces = set()

    for face_id, label in enumerate(model.face_labels):
        if label == 15:  # Stock
            stock_faces.add(face_id)
        else:
            feature_faces.add(face_id)

    logger.info(f"\nModel {model.model_id}:")
    logger.info(f"  Feature faces: {sorted(feature_faces)}")
    logger.info(f"  Stock faces: {sorted(stock_faces)}")

    # Analyze all edges between planar faces
    planar_face_nodes = []
    for node in graph.get_nodes_by_type(TopologyType.FACE):
        if node.attributes.get('surface_type') == SurfaceType.PLANE:
            planar_face_nodes.append(node)

    logger.info(f"\n  Total planar faces: {len(planar_face_nodes)}")

    # Analyze adjacencies and dihedral angles
    feature_to_feature_edges = []
    feature_to_stock_edges = []
    stock_to_stock_edges = []

    for node in planar_face_nodes:
        # Get STEP face ID
        if not node.node_id.startswith("face_"):
            continue

        try:
            face_id = int(node.node_id.split("_")[1])
        except:
            continue

        is_feature = face_id in feature_faces

        # Check adjacent faces
        for adj in graph.get_neighbors(node.node_id):
            if not adj.node_id.startswith("face_"):
                continue

            if adj.attributes.get('surface_type') != SurfaceType.PLANE:
                continue

            try:
                adj_face_id = int(adj.node_id.split("_")[1])
            except:
                continue

            adj_is_feature = adj_face_id in feature_faces

            # Get dihedral angle
            dihedral = graph.get_cached_dihedral_angle(node.node_id, adj.node_id)
            if dihedral is None:
                dihedral = graph.get_cached_dihedral_angle(adj.node_id, node.node_id)

            if dihedral is None:
                continue

            # Categorize edge
            edge_info = (face_id, adj_face_id, dihedral)

            if is_feature and adj_is_feature:
                feature_to_feature_edges.append(edge_info)
            elif is_feature and not adj_is_feature:
                feature_to_stock_edges.append(edge_info)
            elif not is_feature and not adj_is_feature:
                stock_to_stock_edges.append(edge_info)

    # Report findings
    logger.info("\n" + "=" * 80)
    logger.info("FEATURE-TO-FEATURE EDGES (should be concave if same feature):")
    logger.info("=" * 80)
    for f1, f2, angle in sorted(feature_to_feature_edges):
        logger.info(f"  Face {f1} <-> Face {f2}: {angle:.1f}°")

    logger.info("\n" + "=" * 80)
    logger.info("FEATURE-TO-STOCK EDGES (boundary - expect convex ~90°):")
    logger.info("=" * 80)
    for f1, f2, angle in sorted(feature_to_stock_edges):
        logger.info(f"  Face {f1} (feature) <-> Face {f2} (stock): {angle:.1f}°")

    logger.info("\n" + "=" * 80)
    logger.info("STOCK-TO-STOCK EDGES (should be flat ~180° or convex):")
    logger.info("=" * 80)
    # Only show first 10 to avoid spam
    for f1, f2, angle in sorted(stock_to_stock_edges)[:10]:
        logger.info(f"  Face {f1} <-> Face {f2}: {angle:.1f}°")
    if len(stock_to_stock_edges) > 10:
        logger.info(f"  ... and {len(stock_to_stock_edges) - 10} more")

    # Statistics
    if feature_to_feature_edges:
        ff_angles = [a for _, _, a in feature_to_feature_edges]
        logger.info(f"\nFeature-to-Feature angles: min={min(ff_angles):.1f}°, max={max(ff_angles):.1f}°, avg={sum(ff_angles)/len(ff_angles):.1f}°")

    if feature_to_stock_edges:
        fs_angles = [a for _, _, a in feature_to_stock_edges]
        logger.info(f"Feature-to-Stock angles: min={min(fs_angles):.1f}°, max={max(fs_angles):.1f}°, avg={sum(fs_angles)/len(fs_angles):.1f}°")

    if stock_to_stock_edges:
        ss_angles = [a for _, _, a in stock_to_stock_edges]
        logger.info(f"Stock-to-Stock angles: min={min(ss_angles):.1f}°, max={max(ss_angles):.1f}°, avg={sum(ss_angles)/len(ss_angles):.1f}°")


def main():
    """Analyze dihedral angles on first few models."""

    loader = MFCADLoader("/tmp/MFCAD/dataset/step")
    model_ids = loader.get_all_model_ids()[:5]

    for model_id in model_ids:
        try:
            model = loader.load_model(model_id)

            # Skip models with no features
            feature_count = sum(1 for label in model.face_labels if label != 15)
            if feature_count == 0:
                logger.info(f"Skipping {model_id} (no features)")
                continue

            analyze_model_boundaries(model)

            # Analyze first 2 models with features
            return

        except Exception as e:
            logger.error(f"Failed on {model_id}: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
