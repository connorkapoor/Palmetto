"""
MFCAD Graph Dataset for GNN training.

Loads MFCAD models and converts them to PyTorch Geometric graphs.
"""

import logging
from typing import List, Optional
from pathlib import Path

import torch
from torch_geometric.data import Dataset, Data

from app.testing.mfcad_loader import MFCADLoader
from app.core.topology.builder import AAGBuilder
from app.ml.graph_converter import AAGToGraphConverter

logger = logging.getLogger(__name__)


class MFCADGraphDataset(Dataset):
    """
    PyTorch Geometric dataset for MFCAD models.

    Each sample is a graph representing one CAD model, with:
    - Nodes: Planar faces
    - Edges: Face adjacencies
    - Node features: Geometric properties (normal, area, dihedrals, etc.)
    - Edge features: Dihedral angles
    - Node labels: Binary (feature vs stock)
    """

    def __init__(
        self,
        dataset_path: str = "/tmp/MFCAD/dataset/step",
        model_ids: Optional[List[str]] = None,
        transform=None,
        pre_transform=None
    ):
        """
        Initialize MFCAD graph dataset.

        Args:
            dataset_path: Path to MFCAD dataset
            model_ids: List of model IDs to include (if None, use all)
            transform: Optional transform applied to each graph
            pre_transform: Optional pre-transform
        """
        self.loader = MFCADLoader(dataset_path)
        self.converter = AAGToGraphConverter()

        # Get model IDs
        if model_ids is None:
            self.model_ids = self.loader.get_all_model_ids()
        else:
            self.model_ids = model_ids

        logger.info(f"Initialized MFCADGraphDataset with {len(self.model_ids)} models")

        super().__init__(root=None, transform=transform, pre_transform=pre_transform)

    def len(self) -> int:
        """Return number of graphs in dataset."""
        return len(self.model_ids)

    def get(self, idx: int) -> Data:
        """
        Load and convert a model to a graph.

        Args:
            idx: Index of model

        Returns:
            PyTorch Geometric Data object
        """
        model_id = self.model_ids[idx]

        try:
            # Load model
            model = self.loader.load_model(model_id)

            # Build AAG
            aag_builder = AAGBuilder(model.shape)
            aag = aag_builder.build()

            # Convert to PyG graph
            data = self.converter.convert(aag, model.face_labels)

            return data

        except Exception as e:
            logger.error(f"Failed to load model {model_id}: {e}")
            # Return empty graph
            return self.converter._empty_graph()

    def get_train_test_split(
        self,
        train_ratio: float = 0.7,
        seed: int = 42
    ) -> tuple:
        """
        Split dataset into train/test sets.

        Args:
            train_ratio: Fraction for training
            seed: Random seed

        Returns:
            (train_dataset, test_dataset)
        """
        torch.manual_seed(seed)

        # Shuffle indices
        indices = torch.randperm(len(self.model_ids)).tolist()

        # Split
        n_train = int(len(indices) * train_ratio)
        train_indices = indices[:n_train]
        test_indices = indices[n_train:]

        # Create train/test model ID lists
        train_model_ids = [self.model_ids[i] for i in train_indices]
        test_model_ids = [self.model_ids[i] for i in test_indices]

        train_dataset = MFCADGraphDataset(
            dataset_path=self.loader.dataset_path,
            model_ids=train_model_ids,
            transform=self.transform,
            pre_transform=self.pre_transform
        )

        test_dataset = MFCADGraphDataset(
            dataset_path=self.loader.dataset_path,
            model_ids=test_model_ids,
            transform=self.transform,
            pre_transform=self.pre_transform
        )

        logger.info(f"Split: {len(train_dataset)} train, {len(test_dataset)} test")

        return train_dataset, test_dataset
