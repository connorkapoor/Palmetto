#!/usr/bin/env python3
"""
Verify that ground truth extraction correctly splits features into connected components.
"""

import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.testing.mfcad_loader import MFCADLoader, FEAT_NAMES

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Verify ground truth component extraction."""

    loader = MFCADLoader("/tmp/MFCAD/dataset/step")
    model_id = "0-0-0-0-0-23"

    logger.info(f"Loading model {model_id}...")
    model = loader.load_model(model_id)

    logger.info(f"\nRaw face labels:")
    for face_id, label in enumerate(model.face_labels):
        label_name = FEAT_NAMES[label] if label < len(FEAT_NAMES) else "unknown"
        logger.info(f"  Face {face_id}: {label} ({label_name})")

    logger.info(f"\nGround truth features (after component splitting):")
    gt_features = loader.get_ground_truth_features(model)

    for i, feat in enumerate(gt_features):
        logger.info(f"\nFeature {i}: {feat.feature_type}")
        logger.info(f"  Faces: {sorted(feat.face_ids)}")
        logger.info(f"  Count: {len(feat.face_ids)}")

    logger.info(f"\nTotal features extracted: {len(gt_features)}")


if __name__ == "__main__":
    main()
