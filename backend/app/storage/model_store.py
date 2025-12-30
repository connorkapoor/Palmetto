"""
In-memory storage for CAD models and AAGs.

Stores uploaded CAD models, their AAG representations, and metadata.
Implements a singleton pattern for global access and cleanup policies.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import uuid
import logging

from OCC.Core.TopoDS import TopoDS_Shape

from app.core.topology.graph import AttributedAdjacencyGraph

logger = logging.getLogger(__name__)


@dataclass
class StoredModel:
    """Container for a stored CAD model."""
    model_id: str
    filename: str
    file_format: str
    shape: TopoDS_Shape
    graph: AttributedAdjacencyGraph
    uploaded_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, any] = field(default_factory=dict)

    def touch(self) -> None:
        """Update last accessed time."""
        self.last_accessed = datetime.now()

    def age_seconds(self) -> float:
        """Get age in seconds since upload."""
        return (datetime.now() - self.uploaded_at).total_seconds()

    def idle_seconds(self) -> float:
        """Get idle time in seconds since last access."""
        return (datetime.now() - self.last_accessed).total_seconds()


class ModelStore:
    """
    In-memory storage for CAD models.

    Implements singleton pattern for global access.
    Provides automatic cleanup of expired models.
    """

    _instance: Optional['ModelStore'] = None
    _models: Dict[str, StoredModel] = {}

    def __new__(cls):
        """Ensure singleton instance."""
        if cls._instance is None:
            cls._instance = super(ModelStore, cls).__new__(cls)
        return cls._instance

    @classmethod
    def store(
        cls,
        shape: TopoDS_Shape,
        graph: AttributedAdjacencyGraph,
        filename: str,
        file_format: str,
        metadata: Optional[Dict[str, any]] = None
    ) -> str:
        """
        Store a CAD model and its AAG.

        Args:
            shape: B-Rep shape
            graph: Attributed adjacency graph
            filename: Original filename
            file_format: File format (step, iges, brep)
            metadata: Optional metadata dictionary

        Returns:
            Generated model_id
        """
        model_id = str(uuid.uuid4())

        model = StoredModel(
            model_id=model_id,
            filename=filename,
            file_format=file_format,
            shape=shape,
            graph=graph,
            metadata=metadata or {}
        )

        cls._models[model_id] = model

        logger.info(f"Stored model {model_id} ({filename}, {file_format})")
        logger.debug(f"Model stats: {graph.get_statistics()}")

        # Cleanup old models if needed
        cls._cleanup_if_needed()

        return model_id

    @classmethod
    def get(cls, model_id: str) -> Optional[StoredModel]:
        """
        Get a stored model by ID.

        Args:
            model_id: Model identifier

        Returns:
            StoredModel or None if not found
        """
        model = cls._models.get(model_id)
        if model:
            model.touch()  # Update last accessed time
        return model

    @classmethod
    def get_shape(cls, model_id: str) -> Optional[TopoDS_Shape]:
        """
        Get the B-Rep shape for a model.

        Args:
            model_id: Model identifier

        Returns:
            TopoDS_Shape or None if not found
        """
        model = cls.get(model_id)
        return model.shape if model else None

    @classmethod
    def get_graph(cls, model_id: str) -> Optional[AttributedAdjacencyGraph]:
        """
        Get the AAG for a model.

        Args:
            model_id: Model identifier

        Returns:
            AttributedAdjacencyGraph or None if not found
        """
        model = cls.get(model_id)
        return model.graph if model else None

    @classmethod
    def delete(cls, model_id: str) -> bool:
        """
        Delete a model from storage.

        Args:
            model_id: Model identifier

        Returns:
            True if deleted, False if not found
        """
        if model_id in cls._models:
            model = cls._models[model_id]
            del cls._models[model_id]
            logger.info(f"Deleted model {model_id} ({model.filename})")
            return True
        return False

    @classmethod
    def list_models(cls) -> List[Dict[str, any]]:
        """
        List all stored models with metadata.

        Returns:
            List of model information dictionaries
        """
        result = []
        for model in cls._models.values():
            stats = model.graph.get_statistics()
            result.append({
                'model_id': model.model_id,
                'filename': model.filename,
                'file_format': model.file_format,
                'uploaded_at': model.uploaded_at.isoformat(),
                'last_accessed': model.last_accessed.isoformat(),
                'age_seconds': model.age_seconds(),
                'idle_seconds': model.idle_seconds(),
                'topology_stats': stats,
                'metadata': model.metadata
            })
        return result

    @classmethod
    def exists(cls, model_id: str) -> bool:
        """
        Check if a model exists.

        Args:
            model_id: Model identifier

        Returns:
            True if model exists
        """
        return model_id in cls._models

    @classmethod
    def count(cls) -> int:
        """
        Get count of stored models.

        Returns:
            Number of models in storage
        """
        return len(cls._models)

    @classmethod
    def clear(cls) -> None:
        """
        Clear all stored models.
        Useful for testing and manual cleanup.
        """
        count = len(cls._models)
        cls._models.clear()
        logger.info(f"Cleared all {count} stored models")

    @classmethod
    def cleanup_expired(cls, max_age_seconds: int = 3600) -> int:
        """
        Remove models older than max_age_seconds.

        Args:
            max_age_seconds: Maximum age in seconds (default 1 hour)

        Returns:
            Number of models removed
        """
        expired_ids = []

        for model_id, model in cls._models.items():
            if model.age_seconds() > max_age_seconds:
                expired_ids.append(model_id)

        for model_id in expired_ids:
            cls.delete(model_id)

        if expired_ids:
            logger.info(f"Cleaned up {len(expired_ids)} expired models")

        return len(expired_ids)

    @classmethod
    def cleanup_idle(cls, max_idle_seconds: int = 1800) -> int:
        """
        Remove models idle longer than max_idle_seconds.

        Args:
            max_idle_seconds: Maximum idle time in seconds (default 30 minutes)

        Returns:
            Number of models removed
        """
        idle_ids = []

        for model_id, model in cls._models.items():
            if model.idle_seconds() > max_idle_seconds:
                idle_ids.append(model_id)

        for model_id in idle_ids:
            cls.delete(model_id)

        if idle_ids:
            logger.info(f"Cleaned up {len(idle_ids)} idle models")

        return len(idle_ids)

    @classmethod
    def _cleanup_if_needed(cls, max_models: int = 10) -> None:
        """
        Cleanup oldest models if count exceeds max_models.

        Args:
            max_models: Maximum number of models to keep
        """
        if len(cls._models) > max_models:
            # Sort by last accessed time (oldest first)
            sorted_models = sorted(
                cls._models.items(),
                key=lambda x: x[1].last_accessed
            )

            # Remove oldest models
            to_remove = len(cls._models) - max_models
            for model_id, _ in sorted_models[:to_remove]:
                cls.delete(model_id)

            logger.info(f"Auto-cleaned {to_remove} oldest models")

    @classmethod
    def get_statistics(cls) -> Dict[str, any]:
        """
        Get storage statistics.

        Returns:
            Dictionary with storage stats
        """
        if not cls._models:
            return {
                'total_models': 0,
                'oldest_model_age_seconds': 0,
                'newest_model_age_seconds': 0,
                'average_age_seconds': 0
            }

        ages = [model.age_seconds() for model in cls._models.values()]

        return {
            'total_models': len(cls._models),
            'oldest_model_age_seconds': max(ages),
            'newest_model_age_seconds': min(ages),
            'average_age_seconds': sum(ages) / len(ages)
        }
