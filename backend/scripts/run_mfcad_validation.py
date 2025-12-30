#!/usr/bin/env python3
"""
Baseline MFCAD Validation Script

Runs existing feature recognizers against MFCAD ground truth
to establish baseline accuracy metrics.
"""

import sys
import os
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.testing.mfcad_loader import MFCADLoader
from app.testing.validation import RecognizerValidator
from app.testing.metrics import MetricsCalculator
from app.recognizers.registry import RecognizerRegistry
from app.recognizers.features.cavities import CavityRecognizer
from app.recognizers.features.planar_mfcad import PlanarMFCADRecognizer
from app.recognizers.features.face_classifier import FaceClassifier

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Run baseline validation on MFCAD dataset."""

    logger.info("=" * 80)
    logger.info("MFCAD BASELINE VALIDATION")
    logger.info("=" * 80)

    # Initialize dataset loader
    logger.info("\n1. Loading MFCAD dataset...")
    loader = MFCADLoader("/tmp/MFCAD/dataset/step")

    # Create stratified sample (1000 models for speed)
    logger.info("2. Creating stratified sample (1000 models)...")
    sample_ids = loader.create_stratified_sample(n_samples=100)  # Start with 100 for testing
    logger.info(f"   Selected {len(sample_ids)} models")

    # Initialize validator
    validator = RecognizerValidator(loader)

    # Test FaceClassifier (face-level classification)
    logger.info("\n3. Testing FaceClassifier...")
    logger.info("   (classifies individual faces, then groups into features)")

    all_results = []

    for i, model_id in enumerate(sample_ids):
        if i % 10 == 0:
            logger.info(f"   Progress: {i}/{len(sample_ids)} models processed...")

        try:
            # Load model
            model = loader.load_model(model_id)

            # Create recognizer (placeholder graph - will be replaced in validate_model)
            from app.core.topology.graph import AttributedAdjacencyGraph
            dummy_graph = AttributedAdjacencyGraph()
            recognizer = FaceClassifier(dummy_graph)

            # Validate
            results = validator.validate_model(recognizer, model)
            all_results.extend(results)

        except Exception as e:
            logger.error(f"   Failed to process {model_id}: {e}")
            continue

    logger.info(f"\n4. Computing metrics from {len(all_results)} validation results...")

    # Compute metrics
    metrics = MetricsCalculator.compute_metrics(all_results)

    # Print report
    MetricsCalculator.print_report(metrics, detailed=True)

    # Save results
    output_file = Path(__file__).parent.parent / "validation_results" / "face_classifier_v1.txt"
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w') as f:
        import io
        from contextlib import redirect_stdout
        with redirect_stdout(f):
            MetricsCalculator.print_report(metrics, detailed=True)

    logger.info(f"\n5. Results saved to: {output_file}")

    # Check if we meet targets
    logger.info("\n" + "=" * 80)
    logger.info("TARGET CHECK (85% accuracy required)")
    logger.info("=" * 80)

    if metrics.overall_accuracy >= 0.85:
        logger.info(f"✓ Overall Accuracy: {metrics.overall_accuracy:.2%} >= 85% TARGET MET!")
    else:
        logger.warning(f"✗ Overall Accuracy: {metrics.overall_accuracy:.2%} < 85% - NEEDS IMPROVEMENT")

    if metrics.macro_f1 >= 0.80:
        logger.info(f"✓ Macro F1 Score: {metrics.macro_f1:.2%} >= 80% TARGET MET!")
    else:
        logger.warning(f"✗ Macro F1 Score: {metrics.macro_f1:.2%} < 80% - NEEDS IMPROVEMENT")

    logger.info("=" * 80)


if __name__ == "__main__":
    main()
