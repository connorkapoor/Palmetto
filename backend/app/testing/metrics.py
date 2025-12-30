"""
Metrics Calculation - Compute precision, recall, F1, accuracy from validation results.
"""

import logging
from typing import List, Dict
from collections import defaultdict

from .models import ValidationResult, FeatureTypeMetrics, MetricsReport
from .taxonomy_mapper import TaxonomyMapper

logger = logging.getLogger(__name__)


class MetricsCalculator:
    """
    Calculates accuracy metrics from validation results.

    Computes:
    - Overall accuracy
    - Per-feature precision, recall, F1
    - Confusion matrix
    - Stock false positive rate
    """

    @staticmethod
    def compute_metrics(results: List[ValidationResult]) -> MetricsReport:
        """
        Compute complete metrics report from validation results.

        Args:
            results: List of validation results (TP, FP, FN)

        Returns:
            MetricsReport with all metrics
        """
        # Group results by feature type
        per_type_results: Dict[str, List[ValidationResult]] = defaultdict(list)

        for result in results:
            if result.match_type == "TP":
                # Use ground truth type
                feature_type = result.ground_truth.palmetto_type
            elif result.match_type == "FP":
                # Use predicted type
                feature_type = result.predicted.feature_type.value
            elif result.match_type == "FN":
                # Use ground truth type
                feature_type = result.ground_truth.palmetto_type
            else:
                continue

            per_type_results[feature_type].append(result)

        # Compute per-feature metrics
        per_feature_metrics: Dict[str, FeatureTypeMetrics] = {}

        for feature_type, type_results in per_type_results.items():
            metrics = FeatureTypeMetrics(feature_type=feature_type)

            for result in type_results:
                if result.match_type == "TP":
                    metrics.true_positives += 1
                elif result.match_type == "FP":
                    metrics.false_positives += 1
                elif result.match_type == "FN":
                    metrics.false_negatives += 1

            per_feature_metrics[feature_type] = metrics

        # Compute overall accuracy
        total_tp = sum(m.true_positives for m in per_feature_metrics.values())
        total_fp = sum(m.false_positives for m in per_feature_metrics.values())
        total_fn = sum(m.false_negatives for m in per_feature_metrics.values())

        total_samples = total_tp + total_fp + total_fn
        overall_accuracy = total_tp / total_samples if total_samples > 0 else 0.0

        # Compute macro-averaged metrics
        precisions = [m.precision for m in per_feature_metrics.values() if m.precision > 0]
        recalls = [m.recall for m in per_feature_metrics.values() if m.recall > 0]
        f1s = [m.f1_score for m in per_feature_metrics.values() if m.f1_score > 0]

        macro_precision = sum(precisions) / len(precisions) if precisions else 0.0
        macro_recall = sum(recalls) / len(recalls) if recalls else 0.0
        macro_f1 = sum(f1s) / len(f1s) if f1s else 0.0

        # Build confusion matrix
        confusion_matrix = MetricsCalculator._build_confusion_matrix(results)

        # Stock false positive rate (placeholder - needs stock face tracking)
        stock_fp_rate = 0.0

        return MetricsReport(
            overall_accuracy=overall_accuracy,
            per_feature_metrics=per_feature_metrics,
            confusion_matrix=confusion_matrix,
            macro_precision=macro_precision,
            macro_recall=macro_recall,
            macro_f1=macro_f1,
            stock_false_positive_rate=stock_fp_rate,
            total_samples=total_samples,
            total_correct=total_tp,
            total_incorrect=total_fp + total_fn
        )

    @staticmethod
    def _build_confusion_matrix(results: List[ValidationResult]) -> Dict[str, Dict[str, int]]:
        """
        Build confusion matrix: predicted_type → {actual_type → count}

        Args:
            results: Validation results

        Returns:
            Nested dict for confusion matrix
        """
        matrix: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

        for result in results:
            if result.match_type == "TP":
                # Correct prediction
                pred_type = result.predicted.feature_type.value
                actual_type = result.ground_truth.palmetto_type
                matrix[pred_type][actual_type] += 1

            elif result.match_type == "FP":
                # False positive - predicted something that doesn't exist
                pred_type = result.predicted.feature_type.value
                matrix[pred_type]["<none>"] += 1

            elif result.match_type == "FN":
                # False negative - missed a ground truth feature
                actual_type = result.ground_truth.palmetto_type
                matrix["<missed>"][actual_type] += 1

        return {k: dict(v) for k, v in matrix.items()}

    @staticmethod
    def print_report(metrics: MetricsReport, detailed: bool = True):
        """
        Print human-readable metrics report.

        Args:
            metrics: Metrics report to print
            detailed: Whether to include per-feature breakdown
        """
        print("\n" + "=" * 80)
        print("FEATURE RECOGNITION VALIDATION REPORT")
        print("=" * 80)

        # Overall metrics
        print(f"\nOverall Accuracy: {metrics.overall_accuracy:.2%}")
        print(f"Macro Precision:  {metrics.macro_precision:.2%}")
        print(f"Macro Recall:     {metrics.macro_recall:.2%}")
        print(f"Macro F1 Score:   {metrics.macro_f1:.2%}")

        print(f"\nTotal Samples:    {metrics.total_samples}")
        print(f"Correct:          {metrics.total_correct}")
        print(f"Incorrect:        {metrics.total_incorrect}")

        if detailed and metrics.per_feature_metrics:
            print("\n" + "-" * 80)
            print("PER-FEATURE PERFORMANCE")
            print("-" * 80)

            # Header
            print(f"{'Feature Type':<30} {'Precision':>10} {'Recall':>10} {'F1 Score':>10} {'TP':>6} {'FP':>6} {'FN':>6}")
            print("-" * 80)

            # Sort by F1 score (descending)
            sorted_features = sorted(
                metrics.per_feature_metrics.items(),
                key=lambda x: x[1].f1_score,
                reverse=True
            )

            for feature_type, m in sorted_features:
                print(f"{feature_type:<30} "
                      f"{m.precision:>9.2%} "
                      f"{m.recall:>9.2%} "
                      f"{m.f1_score:>9.2%} "
                      f"{m.true_positives:>6} "
                      f"{m.false_positives:>6} "
                      f"{m.false_negatives:>6}")

        # Confusion matrix summary
        if metrics.confusion_matrix:
            print("\n" + "-" * 80)
            print("CONFUSION MATRIX SUMMARY")
            print("-" * 80)
            print("Top misclassifications:")

            # Find top 5 confusion pairs
            confusions = []
            for pred_type, actuals in metrics.confusion_matrix.items():
                for actual_type, count in actuals.items():
                    if pred_type != actual_type and actual_type != "<none>" and pred_type != "<missed>":
                        confusions.append((count, pred_type, actual_type))

            for count, pred, actual in sorted(confusions, reverse=True)[:5]:
                print(f"  {pred} ← {actual}: {count} times")

        print("\n" + "=" * 80)
