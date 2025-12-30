#!/usr/bin/env python3
"""
Debug script to understand how ground truth groups faces vs our algorithm.

Analyzes specific models to see:
1. How ground truth groups faces into features
2. How our algorithm groups faces
3. What the differences are
"""

import sys
import logging
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.testing.mfcad_loader import MFCADLoader, FEAT_NAMES
from app.core.topology.builder import AAGBuilder
from app.core.topology.graph import AttributedAdjacencyGraph
from app.core.topology.attributes import SurfaceType
from app.recognizers.features.planar_mfcad import PlanarMFCADRecognizer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def analyze_ground_truth_grouping(model):
    """Analyze how ground truth groups faces."""

    # Group faces by feature label
    feature_groups = defaultdict(list)
    for face_id, label in enumerate(model.face_labels):
        if label != 15:  # Skip stock
            feature_groups[label].append(face_id)

    logger.info(f"\nGround Truth Features for {model.model_id}:")
    logger.info("=" * 80)

    for label_idx, face_ids in sorted(feature_groups.items()):
        feature_name = FEAT_NAMES[label_idx]
        logger.info(f"\n{feature_name} (label {label_idx}):")
        logger.info(f"  Faces: {sorted(face_ids)}")
        logger.info(f"  Count: {len(face_ids)} faces")

    logger.info(f"\nTotal ground truth features: {len(feature_groups)}")
    logger.info(f"Note: MFCAD labels all faces of a feature TYPE with the same label,")
    logger.info(f"      even if they belong to multiple INSTANCES of that feature.")

    return feature_groups


def analyze_algorithm_grouping(model):
    """Analyze how our algorithm groups faces."""

    # Build AAG
    aag_builder = AAGBuilder(model.shape)
    graph = aag_builder.build()

    # Run recognizer
    recognizer = PlanarMFCADRecognizer(graph)

    # Get planar faces
    planar_faces = recognizer._find_planar_faces()
    logger.info(f"\nFound {len(planar_faces)} planar faces in AAG")

    # Group them
    groups = recognizer._group_connected_planar_faces(planar_faces)

    logger.info(f"\nAlgorithm Grouping:")
    logger.info("=" * 80)

    for i, group in enumerate(groups):
        # Extract STEP face IDs from AAG node IDs
        face_ids = []
        for node in group:
            # AAG nodes are named "face_X" where X is STEP ID
            if node.node_id.startswith("face_"):
                try:
                    step_id = int(node.node_id.split("_")[1])
                    face_ids.append(step_id)
                except:
                    pass

        logger.info(f"\nGroup {i}:")
        logger.info(f"  Faces: {sorted(face_ids)}")
        logger.info(f"  Count: {len(face_ids)} faces")

    return groups


def compare_groupings(model):
    """Compare ground truth vs algorithm groupings."""

    logger.info("\n" + "=" * 80)
    logger.info(f"ANALYZING MODEL: {model.model_id}")
    logger.info("=" * 80)

    # Analyze ground truth
    gt_groups = analyze_ground_truth_grouping(model)

    # Analyze algorithm
    algo_groups = analyze_algorithm_grouping(model)

    logger.info("\n" + "=" * 80)
    logger.info("COMPARISON SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Ground Truth: {len(gt_groups)} features")
    logger.info(f"Algorithm: {len(algo_groups)} groups")
    logger.info("")


def main():
    """Debug face grouping on specific models."""

    loader = MFCADLoader("/tmp/MFCAD/dataset/step")

    # Analyze first few models with features
    model_ids = loader.get_all_model_ids()[:10]

    for model_id in model_ids:
        try:
            model = loader.load_model(model_id)

            # Skip models with only stock faces
            non_stock_count = sum(1 for label in model.face_labels if label != 15)
            if non_stock_count == 0:
                logger.info(f"Skipping {model_id} (no features)")
                continue

            compare_groupings(model)

            # Only analyze first 3 models with features
            break

        except Exception as e:
            logger.error(f"Failed on {model_id}: {e}")
            import traceback
            traceback.print_exc()
            continue


if __name__ == "__main__":
    main()
