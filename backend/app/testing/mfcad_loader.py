"""
MFCAD Dataset Loader

Loads STEP CAD models with ground truth face labels from the MFCAD dataset.
"""

import os
import pickle
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from collections import defaultdict

from OCC.Core.STEPControl import STEPControl_Reader
from OCC.Core.StepRepr import StepRepr_RepresentationItem
from OCC.Core.TopAbs import TopAbs_FACE
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopoDS import topods, TopoDS_Face

from .models import MFCADModel, GroundTruthFeature

logger = logging.getLogger(__name__)


# MFCAD feature taxonomy (from dataset_visualizer.py)
FEAT_NAMES = [
    'rectangular_through_slot',      # 0
    'triangular_through_slot',       # 1
    'rectangular_passage',           # 2
    'triangular_passage',            # 3
    '6sides_passage',                # 4
    'rectangular_through_step',      # 5
    '2sides_through_step',           # 6
    'slanted_through_step',          # 7
    'rectangular_blind_step',        # 8
    'triangular_blind_step',         # 9
    'rectangular_blind_slot',        # 10
    'rectangular_pocket',            # 11
    'triangular_pocket',             # 12
    '6sides_pocket',                 # 13
    'chamfer',                       # 14
    'stock'                          # 15 (base material)
]


class MFCADLoader:
    """
    Loads MFCAD STEP models with ground truth face labels.

    The MFCAD dataset provides:
    - .step files: CAD geometry (ISO 10303-21 B-Rep)
    - .face_truth files: Ground truth labels (Python pickle)

    Each .face_truth file contains a list of integers (0-15) where:
    - List index = Face ID from STEP file
    - List value = Feature type index (0-15)
    """

    def __init__(self, dataset_path: str = "/tmp/MFCAD/dataset/step"):
        """
        Initialize MFCAD loader.

        Args:
            dataset_path: Path to MFCAD dataset/step directory
        """
        self.dataset_path = Path(dataset_path)
        if not self.dataset_path.exists():
            raise ValueError(f"Dataset path does not exist: {dataset_path}")

        self._step_files = sorted(self.dataset_path.glob("*.step"))
        logger.info(f"Found {len(self._step_files)} STEP files in dataset")

    def get_all_model_ids(self) -> List[str]:
        """Get list of all model IDs in dataset."""
        return [f.stem for f in self._step_files]

    def load_model(self, model_id: str) -> MFCADModel:
        """
        Load a single MFCAD model with ground truth labels.

        Args:
            model_id: Model identifier (e.g., "0-0-0-0-0-23")

        Returns:
            MFCADModel with parsed geometry and labels

        Raises:
            FileNotFoundError: If STEP or label file not found
            ValueError: If parsing fails
        """
        step_file = self.dataset_path / f"{model_id}.step"
        label_file = self.dataset_path / f"{model_id}.face_truth"

        if not step_file.exists():
            raise FileNotFoundError(f"STEP file not found: {step_file}")
        if not label_file.exists():
            raise FileNotFoundError(f"Label file not found: {label_file}")

        # Parse STEP file
        shape, face_id_map = self._load_step_with_face_ids(str(step_file))

        # Load ground truth labels
        with open(label_file, 'rb') as f:
            face_labels = pickle.load(f)

        # Convert labels to names
        label_names = [FEAT_NAMES[label_idx] for label_idx in face_labels]

        return MFCADModel(
            model_id=model_id,
            step_file=str(step_file),
            shape=shape,
            face_count=len(face_id_map),
            face_labels=face_labels,
            face_id_map=face_id_map,
            label_names=label_names
        )

    def _load_step_with_face_ids(self, step_file: str) -> Tuple[any, Dict[int, TopoDS_Face]]:
        """
        Load STEP file and extract face IDs.

        Face IDs are stored as entity names in the STEP file.
        This mapping is critical for aligning ground truth labels.

        Args:
            step_file: Path to STEP file

        Returns:
            Tuple of (shape, face_id_map)
            - shape: TopoDS_Shape (B-Rep geometry)
            - face_id_map: Dict mapping face_id (int) → TopoDS_Face
        """
        # Read STEP file
        reader = STEPControl_Reader()
        status = reader.ReadFile(step_file)
        if status != 1:  # IFSelect_RetDone
            raise ValueError(f"Failed to read STEP file: {step_file}")

        reader.TransferRoots()
        shape = reader.OneShape()

        # Extract face IDs from STEP entities
        face_id_map = {}
        treader = reader.WS().TransferReader()

        # Get all faces from shape
        faces = self._get_all_faces(shape)

        for face in faces:
            # Get corresponding STEP entity
            item = treader.EntityFromShapeResult(face, 1)
            if item is None:
                continue

            # Downcast to RepresentationItem to get name
            item = StepRepr_RepresentationItem.DownCast(item)
            if item is None:
                continue

            # Extract numeric face ID from name
            name_str = item.Name().ToCString()
            if name_str:
                try:
                    face_id = int(name_str)
                    face_id_map[face_id] = face
                except ValueError:
                    # Some faces might not have numeric names
                    pass

        logger.debug(f"Extracted {len(face_id_map)} face IDs from STEP file")
        return shape, face_id_map

    def _get_all_faces(self, shape) -> List[TopoDS_Face]:
        """Extract all faces from a shape."""
        faces = []
        explorer = TopExp_Explorer(shape, TopAbs_FACE)
        while explorer.More():
            face = topods.Face(explorer.Current())
            faces.append(face)
            explorer.Next()
        return faces

    def get_ground_truth_features(self, model: MFCADModel) -> List[GroundTruthFeature]:
        """
        Extract ground truth features from a loaded model.

        Groups adjacent faces with the same label into feature instances.

        Important: MFCAD labels are per FACE, not per feature instance.
        Multiple instances of the same feature type will have the same label.
        We must split them into connected components.

        Args:
            model: Loaded MFCAD model

        Returns:
            List of ground truth features (one per instance)
        """
        from OCC.Core.TopExp import TopExp_Explorer
        from OCC.Core.TopAbs import TopAbs_EDGE
        from OCC.Core.TopTools import TopTools_IndexedDataMapOfShapeListOfShape
        from OCC.Core.TopExp import topexp

        features = []

        # Group faces by label first
        label_to_faces: Dict[int, List[int]] = defaultdict(list)
        for face_id in sorted(model.face_id_map.keys()):
            label_idx = model.face_labels[face_id]
            label_to_faces[label_idx].append(face_id)

        # Build face adjacency map (which faces share edges)
        face_adjacency: Dict[int, List[int]] = defaultdict(list)

        # Map: Edge -> Faces
        edge_to_faces: Dict[int, List[int]] = defaultdict(list)
        for face_id, face in model.face_id_map.items():
            # Find edges of this face
            edge_exp = TopExp_Explorer(face, TopAbs_EDGE)
            while edge_exp.More():
                edge = edge_exp.Current()
                edge_hash = edge.__hash__()
                edge_to_faces[edge_hash].append(face_id)
                edge_exp.Next()

        # Build adjacency: faces sharing an edge are adjacent
        for edge_hash, faces in edge_to_faces.items():
            if len(faces) == 2:
                f1, f2 = faces
                face_adjacency[f1].append(f2)
                face_adjacency[f2].append(f1)

        # For each label, split faces into connected components
        for label_idx, all_face_ids in label_to_faces.items():
            # Skip stock (label 15)
            if label_idx == 15:
                continue

            # BFS to find connected components
            visited = set()
            components = []

            for start_face in all_face_ids:
                if start_face in visited:
                    continue

                # BFS from this face
                component = []
                queue = [start_face]
                visited.add(start_face)

                while queue:
                    current_face = queue.pop(0)
                    component.append(current_face)

                    # Check adjacent faces
                    for adj_face in face_adjacency[current_face]:
                        # Only traverse if same label and not visited
                        if adj_face in all_face_ids and adj_face not in visited:
                            visited.add(adj_face)
                            queue.append(adj_face)

                components.append(component)

            # Create one GroundTruthFeature per connected component
            for component_faces in components:
                feature = GroundTruthFeature(
                    feature_type=FEAT_NAMES[label_idx],
                    feature_type_index=label_idx,
                    face_ids=component_faces,
                    properties={}
                )
                features.append(feature)

        return features

    def create_stratified_sample(self, n_samples: int = 1000, seed: int = 42) -> List[str]:
        """
        Create a stratified sample of model IDs ensuring all feature types represented.

        Args:
            n_samples: Number of models to sample
            seed: Random seed for reproducibility

        Returns:
            List of model IDs
        """
        import random
        random.seed(seed)

        # First, categorize models by which feature types they contain
        # This requires loading all labels (fast - just pickle files)
        feature_type_models: Dict[int, List[str]] = defaultdict(list)

        for model_id in self.get_all_model_ids():
            label_file = self.dataset_path / f"{model_id}.face_truth"
            try:
                with open(label_file, 'rb') as f:
                    labels = pickle.load(f)

                # Track unique feature types in this model (excluding stock)
                unique_labels = set(labels) - {15}
                for label in unique_labels:
                    feature_type_models[label].append(model_id)
            except Exception as e:
                logger.warning(f"Failed to load labels for {model_id}: {e}")

        # Ensure each feature type gets proportional representation
        sampled_models = set()

        # First pass: ensure at least some models for each feature type
        min_per_type = max(10, n_samples // len(FEAT_NAMES))
        for feature_type, models in feature_type_models.items():
            n_to_sample = min(min_per_type, len(models))
            sampled = random.sample(models, n_to_sample)
            sampled_models.update(sampled)

        # Second pass: fill remaining quota randomly
        all_model_ids = self.get_all_model_ids()
        remaining = set(all_model_ids) - sampled_models
        n_remaining = n_samples - len(sampled_models)
        if n_remaining > 0 and len(remaining) > 0:
            additional = random.sample(list(remaining), min(n_remaining, len(remaining)))
            sampled_models.update(additional)

        result = list(sampled_models)
        logger.info(f"Created stratified sample of {len(result)} models")
        return result
