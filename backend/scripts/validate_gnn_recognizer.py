"""
Validate GNN Recognizer on MFCAD test set.

Runs end-to-end: AAG -> GNN inference -> Feature grouping -> Instance metrics
"""

import logging
from pathlib import Path
import sys

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.testing.mfcad_loader import MFCADLoader
from app.recognizers.features.gnn_recognizer import GNNRecognizer
from app.testing.validation import RecognizerValidator
from app.testing.metrics import MetricsCalculator
from app.core.topology.graph import AttributedAdjacencyGraph

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    # Load dataset
    loader = MFCADLoader("/tmp/MFCAD/dataset/step")

    # Get test split (same as training - models 700-999)
    all_ids = loader.get_all_model_ids()[:1000]  # Same 1000 used in training
    test_ids = all_ids[700:]  # 300 test models

    logger.info(f"Testing on {len(test_ids)} models")

    # Initialize validator
    validator = RecognizerValidator(loader)
    metrics_calc = MetricsCalculator()

    # Track results
    all_results = []

    # Process each test model
    for i, model_id in enumerate(test_ids):
        if (i + 1) % 50 == 0:
            logger.info(f"Processed {i + 1}/{len(test_ids)} models")

        try:
            # Load model
            model = loader.load_model(model_id)

            # Create recognizer instance (placeholder graph - will be replaced in validate_model)
            dummy_graph = AttributedAdjacencyGraph()
            recognizer = GNNRecognizer(dummy_graph)

            # Validate using RecognizerValidator API
            results = validator.validate_model(recognizer, model)
            all_results.extend(results)

        except Exception as e:
            logger.error(f"Failed on {model_id}: {e}")
            import traceback
            traceback.print_exc()
            continue

    # Compute overall metrics
    logger.info("\n" + "="*60)
    logger.info("GNN RECOGNIZER VALIDATION RESULTS")
    logger.info("="*60)

    metrics = metrics_calc.compute_metrics(all_results)

    logger.info(f"\nOverall Performance:")
    logger.info(f"  Accuracy:  {metrics.overall_accuracy:.2%}")
    logger.info(f"  Macro Precision: {metrics.macro_precision:.2%}")
    logger.info(f"  Macro Recall:    {metrics.macro_recall:.2%}")
    logger.info(f"  Macro F1 Score:  {metrics.macro_f1:.2%}")

    logger.info(f"\nCounts:")
    logger.info(f"  Total Samples: {metrics.total_samples}")
    logger.info(f"  Total Correct: {metrics.total_correct}")
    logger.info(f"  Total Incorrect: {metrics.total_incorrect}")

    # Per-type breakdown
    logger.info(f"\nPer-Feature-Type Performance:")
    for ftype, type_metrics in metrics.per_feature_metrics.items():
        logger.info(f"  {ftype:25s} | P: {type_metrics.precision:.2%} R: {type_metrics.recall:.2%} F1: {type_metrics.f1_score:.2%} | TP: {type_metrics.true_positives} FP: {type_metrics.false_positives} FN: {type_metrics.false_negatives}")

    # Compare to target
    logger.info(f"\n" + "="*60)
    target = 0.85
    if metrics.overall_accuracy >= target:
        logger.info(f"✅ TARGET MET: {metrics.overall_accuracy:.2%} >= {target:.0%}")
    else:
        gap = target - metrics.overall_accuracy
        logger.info(f"⚠️  TARGET NOT MET: {metrics.overall_accuracy:.2%} < {target:.0%} (gap: {gap:.2%})")
    logger.info("="*60)

if __name__ == "__main__":
    main()
