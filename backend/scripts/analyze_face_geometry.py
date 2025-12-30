#!/usr/bin/env python3
"""
Analyze geometric properties of feature vs stock faces.

Goal: Find geometric criteria to distinguish feature faces from stock.
"""

import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.testing.mfcad_loader import MFCADLoader, FEAT_NAMES
from app.core.topology.builder import AAGBuilder
from app.core.topology.graph import TopologyType
from app.core.topology.attributes import SurfaceType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def analyze_face_properties(model):
    """Analyze geometric properties of feature vs stock faces."""

    # Build AAG
    aag_builder = AAGBuilder(model.shape)
    graph = aag_builder.build()

    # Separate feature vs stock faces
    feature_face_ids = set()
    stock_face_ids = set()

    for face_id, label in enumerate(model.face_labels):
        if label == 15:
            stock_face_ids.add(face_id)
        else:
            feature_face_ids.add(face_id)

    logger.info(f"\nModel {model.model_id}:")
    logger.info(f"  Feature faces: {sorted(feature_face_ids)}")
    logger.info(f"  Stock faces: {sorted(stock_face_ids)}")

    # Analyze planar face properties
    feature_props = []
    stock_props = []

    for node in graph.get_nodes_by_type(TopologyType.FACE):
        if node.attributes.get('surface_type') != SurfaceType.PLANE:
            continue

        if not node.node_id.startswith("face_"):
            continue

        try:
            face_id = int(node.node_id.split("_")[1])
        except:
            continue

        # Extract properties
        props = {}
        props['face_id'] = face_id

        center = node.attributes.get('center_of_mass')
        if center:
            props['center_x'] = center.X()
            props['center_y'] = center.Y()
            props['center_z'] = center.Z()

        normal = node.attributes.get('normal')
        if normal:
            props['normal_x'] = normal.X()
            props['normal_y'] = normal.Y()
            props['normal_z'] = normal.Z()

        props['area'] = node.attributes.get('area', 0)

        # Categorize
        if face_id in feature_face_ids:
            feature_props.append(props)
        elif face_id in stock_face_ids:
            stock_props.append(props)

    # Compare properties
    logger.info("\n" + "=" * 80)
    logger.info("FEATURE FACES (slot faces):")
    logger.info("=" * 80)
    for p in feature_props:
        logger.info(f"Face {p['face_id']}:")
        logger.info(f"  Center: ({p.get('center_x', 0):.2f}, {p.get('center_y', 0):.2f}, {p.get('center_z', 0):.2f})")
        logger.info(f"  Normal: ({p.get('normal_x', 0):.2f}, {p.get('normal_y', 0):.2f}, {p.get('normal_z', 0):.2f})")
        logger.info(f"  Area: {p['area']:.2f}")

    logger.info("\n" + "=" * 80)
    logger.info("STOCK FACES (outer box faces):")
    logger.info("=" * 80)
    for p in stock_props:
        logger.info(f"Face {p['face_id']}:")
        logger.info(f"  Center: ({p.get('center_x', 0):.2f}, {p.get('center_y', 0):.2f}, {p.get('center_z', 0):.2f})")
        logger.info(f"  Normal: ({p.get('normal_x', 0):.2f}, {p.get('normal_y', 0):.2f}, {p.get('normal_z', 0):.2f})")
        logger.info(f"  Area: {p['area']:.2f}")

    # Statistics
    if feature_props:
        feature_zs = [p.get('center_z', 0) for p in feature_props]
        logger.info(f"\nFeature Z range: {min(feature_zs):.2f} to {max(feature_zs):.2f}")

    if stock_props:
        stock_zs = [p.get('center_z', 0) for p in stock_props]
        logger.info(f"Stock Z range: {min(stock_zs):.2f} to {max(stock_zs):.2f}")


def main():
    """Analyze geometric properties."""

    loader = MFCADLoader("/tmp/MFCAD/dataset/step")
    model_id = "0-0-0-0-0-23"

    model = loader.load_model(model_id)
    analyze_face_properties(model)


if __name__ == "__main__":
    main()
