"""
Quick test of new hole recognizer on a few MFCAD models.
"""

import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.cad_loader import CADLoader
from app.core.topology.builder import AAGBuilder
from app.recognizers.features.holes_v2 import HoleRecognizerV2
from app.testing.mfcad_loader import MFCADLoader

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Test on first 5 models
mfcad = MFCADLoader("/tmp/MFCAD/dataset/step")
model_ids = mfcad.get_all_model_ids()[:5]

logger.info(f"Testing on {len(model_ids)} models")

for model_id in model_ids:
    logger.info(f"\n{'='*60}")
    logger.info(f"Model: {model_id}")
    logger.info('='*60)

    try:
        # Load model
        model = mfcad.load_model(model_id)

        # Build AAG
        builder = AAGBuilder(model.shape)
        graph = builder.build()

        logger.info(f"AAG: {len(graph.nodes)} nodes, {len(graph.edges)} edges")

        # Get ground truth
        label_counts = {}
        from app.testing.mfcad_loader import FEAT_NAMES
        for label in model.face_labels:
            feat_name = FEAT_NAMES[label]
            label_counts[feat_name] = label_counts.get(feat_name, 0) + 1

        logger.info(f"Ground truth features:")
        for feat_name, count in sorted(label_counts.items()):
            if feat_name != 'stock':
                logger.info(f"  {feat_name}: {count} faces")

        # Run hole recognizer
        recognizer = HoleRecognizerV2(graph)
        holes = recognizer.recognize()

        logger.info(f"\nPredicted: {len(holes)} holes")
        for hole in holes:
            logger.info(f"  {hole.feature_type.value}: {len(hole.face_ids)} faces, {hole.properties}")

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        continue
