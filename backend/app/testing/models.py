"""
Data models for MFCAD dataset integration and validation.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from OCC.Core.TopoDS import TopoDS_Shape, TopoDS_Face


@dataclass
class MFCADModel:
    """
    A loaded MFCAD model with geometry and ground truth labels.
    """
    model_id: str  # e.g., "0-0-0-0-0-23"
    step_file: str  # Path to .step file
    shape: TopoDS_Shape  # Parsed B-Rep geometry
    face_count: int  # Number of faces in model

    # Ground truth data
    face_labels: List[int]  # Raw label indices (0-15) per face
    face_id_map: Dict[int, TopoDS_Face]  # face_id → TopoDS_Face mapping

    # Feature name mapping
    label_names: List[str]  # Human-readable feature names per face


@dataclass
class GroundTruthFeature:
    """
    A ground truth feature annotation from MFCAD dataset.
    """
    feature_type: str  # MFCAD label name (e.g., "rectangular_pocket")
    feature_type_index: int  # MFCAD label index (0-15)
    face_ids: List[int]  # Face IDs that comprise this feature
    properties: Dict[str, Any] = field(default_factory=dict)  # shape, size, etc.

    # Mapped to Palmetto taxonomy
    palmetto_type: Optional[str] = None  # FeatureType enum value
    palmetto_properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    """
    Result of comparing predicted feature vs ground truth.
    """
    model_id: str
    ground_truth: Optional[GroundTruthFeature]  # None for false positive
    predicted: Optional[Any]  # RecognizedFeature, None for false negative
    match_type: str  # "TP", "FP", "FN", "TN"
    iou: float = 0.0  # Intersection over Union of face sets
    type_match: bool = False  # Whether feature types match


@dataclass
class FeatureTypeMetrics:
    """
    Metrics for a single feature type.
    """
    feature_type: str
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0

    @property
    def precision(self) -> float:
        """Precision: TP / (TP + FP)"""
        if self.true_positives + self.false_positives == 0:
            return 0.0
        return self.true_positives / (self.true_positives + self.false_positives)

    @property
    def recall(self) -> float:
        """Recall: TP / (TP + FN)"""
        if self.true_positives + self.false_negatives == 0:
            return 0.0
        return self.true_positives / (self.true_positives + self.false_negatives)

    @property
    def f1_score(self) -> float:
        """F1 Score: 2 * (P * R) / (P + R)"""
        p, r = self.precision, self.recall
        if p + r == 0:
            return 0.0
        return 2 * (p * r) / (p + r)


@dataclass
class MetricsReport:
    """
    Complete validation metrics report.
    """
    overall_accuracy: float
    per_feature_metrics: Dict[str, FeatureTypeMetrics]
    confusion_matrix: Dict[str, Dict[str, int]]  # predicted → {ground_truth → count}

    # Aggregate metrics
    macro_precision: float  # Average precision across all types
    macro_recall: float
    macro_f1: float

    # Stock face validation
    stock_false_positive_rate: float  # % of stock faces misclassified

    # Summary
    total_samples: int
    total_correct: int
    total_incorrect: int
