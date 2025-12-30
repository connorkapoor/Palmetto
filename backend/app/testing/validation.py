"""
Validation Framework - Compare recognizer predictions against ground truth.

This module provides tools to validate feature recognizers against
the MFCAD dataset ground truth labels.
"""

import logging
from typing import List, Set, Optional
from dataclasses import dataclass

from app.recognizers.base import RecognizedFeature, FeatureType, BaseRecognizer
from app.core.topology.builder import AAGBuilder
from .models import MFCADModel, GroundTruthFeature, ValidationResult
from .mfcad_loader import MFCADLoader
from .taxonomy_mapper import TaxonomyMapper

logger = logging.getLogger(__name__)


class RecognizerValidator:
    """
    Validates feature recognizers against MFCAD ground truth.

    Compares predicted features to ground truth by matching face sets
    and computing accuracy metrics.
    """

    def __init__(self, loader: MFCADLoader, iou_threshold: float = 0.5):
        """
        Initialize validator.

        Args:
            loader: MFCAD dataset loader
            iou_threshold: Minimum IoU for feature match (default 0.5)
        """
        self.loader = loader
        self.iou_threshold = iou_threshold

    def validate_model(
        self,
        recognizer: BaseRecognizer,
        model: MFCADModel
    ) -> List[ValidationResult]:
        """
        Validate recognizer on a single model.

        Args:
            recognizer: Feature recognizer to test
            model: MFCAD model with ground truth

        Returns:
            List of validation results (TP, FP, FN)
        """
        # Build AAG from model shape
        aag_builder = AAGBuilder(model.shape)
        graph = aag_builder.build()

        # Run recognition
        # Note: Need to reinitialize recognizer with this graph
        recognizer_class = recognizer.__class__
        model_recognizer = recognizer_class(graph)
        predictions = model_recognizer.recognize()

        # Get ground truth features
        gt_features = self.loader.get_ground_truth_features(model)

        # Map ground truth to Palmetto taxonomy
        gt_mapped = self._map_ground_truth_to_palmetto(gt_features)

        # Compare predictions to ground truth
        results = self._compare_features(
            predictions,
            gt_mapped,
            model.model_id,
            model.face_id_map
        )

        return results

    def _map_ground_truth_to_palmetto(
        self,
        gt_features: List[GroundTruthFeature]
    ) -> List[GroundTruthFeature]:
        """
        Map ground truth features to Palmetto taxonomy.

        Args:
            gt_features: Ground truth features with MFCAD labels

        Returns:
            Ground truth features with Palmetto types assigned
        """
        mapped = []
        for gt in gt_features:
            mapping = TaxonomyMapper.mfcad_to_palmetto(gt.feature_type_index)
            if mapping is not None:
                palmetto_type, properties = mapping
                gt.palmetto_type = palmetto_type.value
                gt.palmetto_properties = properties
                mapped.append(gt)
            # Skip stock features (mapping = None)

        return mapped

    def _compare_features(
        self,
        predictions: List[RecognizedFeature],
        ground_truth: List[GroundTruthFeature],
        model_id: str,
        face_id_map: dict
    ) -> List[ValidationResult]:
        """
        Compare predicted features to ground truth.

        Matching strategy:
        - Compute face IoU (Intersection over Union)
        - Match if IoU >= threshold AND types match
        - Classify as TP, FP, or FN

        Args:
            predictions: Predicted features from recognizer
            ground_truth: Ground truth features
            model_id: Model identifier
            face_id_map: Mapping of face IDs to TopoDS_Face objects

        Returns:
            List of validation results
        """
        results = []

        # Convert face_ids to sets for comparison
        # Note: Predicted face_ids are AAG node IDs (strings like "face_0")
        # Ground truth face_ids are numeric IDs from STEP file

        # Build mapping: AAG face node ID → STEP face ID
        aag_to_step_map = self._build_face_id_mapping(face_id_map)

        # Convert predictions to use STEP face IDs
        pred_with_step_ids = []
        for pred in predictions:
            step_ids = []
            for aag_id in pred.face_ids:
                if aag_id in aag_to_step_map:
                    step_ids.append(aag_to_step_map[aag_id])
            if step_ids:
                pred_with_step_ids.append((pred, set(step_ids)))

        # Convert ground truth to sets
        gt_sets = [(gt, set(gt.face_ids)) for gt in ground_truth]

        # Track matched ground truth
        matched_gt = set()

        # Find true positives
        for pred, pred_faces in pred_with_step_ids:
            best_match = None
            best_iou = 0.0

            for i, (gt, gt_faces) in enumerate(gt_sets):
                if i in matched_gt:
                    continue  # Already matched

                # Compute IoU
                iou = self._compute_iou(pred_faces, gt_faces)

                if iou >= self.iou_threshold and iou > best_iou:
                    # Check if types match
                    if self._types_match(pred.feature_type, gt.palmetto_type):
                        best_match = (i, gt, iou)
                        best_iou = iou

            if best_match is not None:
                # True positive
                i, gt, iou = best_match
                matched_gt.add(i)
                results.append(ValidationResult(
                    model_id=model_id,
                    ground_truth=gt,
                    predicted=pred,
                    match_type="TP",
                    iou=iou,
                    type_match=True
                ))
            else:
                # False positive (no matching ground truth)
                results.append(ValidationResult(
                    model_id=model_id,
                    ground_truth=None,
                    predicted=pred,
                    match_type="FP",
                    iou=0.0,
                    type_match=False
                ))

        # Find false negatives (unmatched ground truth)
        for i, (gt, gt_faces) in enumerate(gt_sets):
            if i not in matched_gt:
                results.append(ValidationResult(
                    model_id=model_id,
                    ground_truth=gt,
                    predicted=None,
                    match_type="FN",
                    iou=0.0,
                    type_match=False
                ))

        return results

    def _build_face_id_mapping(self, face_id_map: dict) -> dict:
        """
        Build mapping from AAG face node IDs to STEP face IDs.

        This is a placeholder - actual implementation requires
        correlating AAG faces with STEP face IDs.

        For now, assume AAG face nodes are named "face_0", "face_1", etc.
        and map to STEP IDs 0, 1, 2, ...
        """
        # Simplified mapping - in reality, this requires more sophisticated correlation
        mapping = {}
        for step_id in sorted(face_id_map.keys()):
            aag_id = f"face_{step_id}"
            mapping[aag_id] = step_id
        return mapping

    def _compute_iou(self, faces1: Set[int], faces2: Set[int]) -> float:
        """
        Compute Intersection over Union of two face sets.

        Args:
            faces1: First set of face IDs
            faces2: Second set of face IDs

        Returns:
            IoU score (0.0 to 1.0)
        """
        if not faces1 or not faces2:
            return 0.0

        intersection = len(faces1 & faces2)
        union = len(faces1 | faces2)

        if union == 0:
            return 0.0

        return intersection / union

    def _types_match(self, pred_type: FeatureType, gt_type: Optional[str]) -> bool:
        """
        Check if predicted type matches ground truth type.

        Args:
            pred_type: Predicted FeatureType
            gt_type: Ground truth type (Palmetto string value)

        Returns:
            True if types match
        """
        if gt_type is None:
            return False
        return pred_type.value == gt_type
