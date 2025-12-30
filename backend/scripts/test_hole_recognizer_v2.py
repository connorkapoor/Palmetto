"""
Test the new Analysis Situs-based hole recognizer against MFCAD dataset.
"""

import sys
import os
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.cad_loader import CADLoader
from app.core.topology.builder import AAGBuilder
from app.recognizers.features.holes_v2 import HoleRecognizerV2
from app.testing.mfcad_loader import MFCADLoader
from app.testing.taxonomy_mapper import TaxonomyMapper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_single_model(step_file: str):
    """Test hole recognizer on a single STEP file."""
    logger.info(f"Testing {step_file}")

    # Load STEP file
    shape = CADLoader.load(step_file)

    if not shape:
        logger.error(f"Failed to load {step_file}")
        return

    # Build AAG
    builder = AAGBuilder(shape)
    graph = builder.build()

    logger.info(f"AAG: {len(graph.nodes)} nodes, {len(graph.edges)} edges")

    # Run hole recognizer
    recognizer = HoleRecognizerV2(graph)
    holes = recognizer.recognize()

    logger.info(f"Found {len(holes)} holes:")
    for hole in holes:
        logger.info(f"  - {hole.feature_type.value}: {hole.properties}")

    return holes


def test_mfcad_sample():
    """Test on MFCAD dataset sample."""
    mfcad_path = "/tmp/MFCAD"

    if not os.path.exists(mfcad_path):
        logger.error(f"MFCAD dataset not found at {mfcad_path}")
        logger.info("Downloading MFCAD dataset...")
        os.system("git clone https://github.com/hducg/MFCAD.git /tmp/MFCAD")

    # Load MFCAD dataset
    mfcad = MFCADLoader(mfcad_path)
    mapper = TaxonomyMapper()

    # Test on first 10 models with holes
    logger.info("Testing on MFCAD models with holes...")

    hole_types = {0, 1, 10}  # rectangular_through_slot, triangular_through_slot, rectangular_blind_slot

    tested = 0
    correct = 0
    false_positives = 0
    false_negatives = 0

    for model in mfcad.iterate_models():
        if tested >= 10:
            break

        # Check if model has any hole-like features
        has_holes = any(label in hole_types for label in model.face_labels.values())
        if not has_holes:
            continue

        logger.info(f"\nTesting {model.model_name}")

        try:
            # Build AAG
            builder = AAGBuilder(model.shape)
            graph = builder.build()

            # Run hole recognizer
            recognizer = HoleRecognizerV2(graph)
            predicted_holes = recognizer.recognize()

            # Get ground truth
            ground_truth = mapper.map_to_features(model)
            gt_holes = [f for f in ground_truth if 'hole' in f.feature_type.value.lower() or
                        'slot' in f.feature_type.value.lower()]

            logger.info(f"  Predicted: {len(predicted_holes)} holes")
            logger.info(f"  Ground truth: {len(gt_holes)} holes")

            # Simple matching by face overlap
            matched = 0
            for pred in predicted_holes:
                pred_faces = set(pred.face_ids)
                for gt in gt_holes:
                    gt_faces = set(gt.face_ids)
                    overlap = len(pred_faces & gt_faces)
                    iou = overlap / len(pred_faces | gt_faces) if pred_faces | gt_faces else 0

                    if iou > 0.5:  # Match if IoU > 50%
                        matched += 1
                        break

            correct += matched
            false_positives += len(predicted_holes) - matched
            false_negatives += len(gt_holes) - matched

            logger.info(f"  Matched: {matched}/{len(gt_holes)}")

            tested += 1

        except Exception as e:
            logger.error(f"Error processing {model.model_name}: {e}")
            continue

    # Report results
    logger.info(f"\n{'='*60}")
    logger.info(f"RESULTS (n={tested} models)")
    logger.info(f"{'='*60}")
    logger.info(f"True Positives: {correct}")
    logger.info(f"False Positives: {false_positives}")
    logger.info(f"False Negatives: {false_negatives}")

    if correct + false_positives > 0:
        precision = correct / (correct + false_positives)
        logger.info(f"Precision: {precision:.2%}")
    if correct + false_negatives > 0:
        recall = correct / (correct + false_negatives)
        logger.info(f"Recall: {recall:.2%}")
    if correct + false_positives + false_negatives > 0:
        f1 = 2 * correct / (2 * correct + false_positives + false_negatives)
        logger.info(f"F1 Score: {f1:.2%}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Test single file
        test_single_model(sys.argv[1])
    else:
        # Test MFCAD sample
        test_mfcad_sample()
