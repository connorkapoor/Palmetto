#!/usr/bin/env python3
"""
Sample multiple models to understand labeling patterns.
"""

import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.testing.mfcad_loader import MFCADLoader, FEAT_NAMES
from app.core.topology.builder import AAGBuilder
from app.core.topology.graph import TopologyType
from app.core.topology.attributes import SurfaceType

logging.basicConfig(level=logging.WARNING)  # Reduce noise
logger = logging.getLogger(__name__)


def quick_analysis(model, loader):
    """Quick analysis of a single model."""

    # Count faces by label
    label_counts = {}
    for label in model.face_labels:
        label_counts[label] = label_counts.get(label, 0) + 1

    # Get ground truth features (with component splitting)
    gt_features = loader.get_ground_truth_features(model)

    print(f"\n{model.model_id}:")
    print(f"  Total faces: {len(model.face_labels)}")

    # Show non-stock labels
    for label, count in sorted(label_counts.items()):
        if label != 15:
            print(f"  {FEAT_NAMES[label]}: {count} faces")

    print(f"  Ground truth features (after splitting): {len(gt_features)}")
    for feat in gt_features:
        print(f"    - {feat.feature_type}: {len(feat.face_ids)} faces {sorted(feat.face_ids)}")


def main():
    """Sample 10 models to understand patterns."""

    loader = MFCADLoader("/tmp/MFCAD/dataset/step")
    model_ids = loader.get_all_model_ids()[:20]

    print("=" * 80)
    print("SAMPLING MFCAD MODELS TO UNDERSTAND LABELING PATTERNS")
    print("=" * 80)

    analyzed = 0
    for model_id in model_ids:
        try:
            model = loader.load_model(model_id)

            # Skip if no features
            has_features = any(label != 15 for label in model.face_labels)
            if not has_features:
                continue

            quick_analysis(model, loader)
            analyzed += 1

            if analyzed >= 10:
                break

        except Exception as e:
            print(f"\nFailed on {model_id}: {e}")
            continue

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
