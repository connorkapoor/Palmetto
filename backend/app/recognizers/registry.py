"""
Recognizer Registry - Plugin system for feature recognizers.

Provides automatic registration and discovery of recognizers via
the @register_recognizer decorator. Recognizers are stored in a
central registry and can be queried by name or capability.
"""

from typing import Dict, List, Optional, Type
import logging

from app.recognizers.base import BaseRecognizer, FeatureType

logger = logging.getLogger(__name__)


class RecognizerRegistry:
    """
    Central registry for all feature recognizers.

    Implements a singleton pattern to ensure a single global registry.
    Recognizers are automatically registered using the @register_recognizer decorator.
    """

    _instance: Optional['RecognizerRegistry'] = None
    _recognizers: Dict[str, Type[BaseRecognizer]] = {}

    def __new__(cls):
        """Ensure singleton instance."""
        if cls._instance is None:
            cls._instance = super(RecognizerRegistry, cls).__new__(cls)
        return cls._instance

    @classmethod
    def register(cls, recognizer_class: Type[BaseRecognizer]) -> None:
        """
        Register a recognizer class.

        Args:
            recognizer_class: Class (not instance) of recognizer to register

        Raises:
            ValueError: If recognizer with same name already registered
        """
        # Create temporary instance to get name
        temp_instance = recognizer_class(None)  # type: ignore
        name = temp_instance.get_name()

        if name in cls._recognizers:
            logger.warning(f"Recognizer '{name}' already registered. Overwriting...")

        cls._recognizers[name] = recognizer_class
        logger.info(f"Registered recognizer: {name}")

    @classmethod
    def unregister(cls, name: str) -> bool:
        """
        Unregister a recognizer by name.

        Args:
            name: Recognizer name

        Returns:
            True if unregistered, False if not found
        """
        if name in cls._recognizers:
            del cls._recognizers[name]
            logger.info(f"Unregistered recognizer: {name}")
            return True
        return False

    @classmethod
    def get(cls, name: str) -> Optional[Type[BaseRecognizer]]:
        """
        Get recognizer class by name.

        Args:
            name: Recognizer name

        Returns:
            Recognizer class or None if not found
        """
        return cls._recognizers.get(name)

    @classmethod
    def list_all(cls) -> List[str]:
        """
        List all registered recognizer names.

        Returns:
            List of recognizer names
        """
        return list(cls._recognizers.keys())

    @classmethod
    def get_all(cls) -> Dict[str, Type[BaseRecognizer]]:
        """
        Get all registered recognizers.

        Returns:
            Dictionary mapping names to recognizer classes
        """
        return cls._recognizers.copy()

    @classmethod
    def get_by_feature_type(cls, feature_type: FeatureType) -> List[Type[BaseRecognizer]]:
        """
        Find recognizers capable of detecting a feature type.

        Args:
            feature_type: FeatureType to search for

        Returns:
            List of recognizer classes that can detect this feature type
        """
        results = []
        for rec_class in cls._recognizers.values():
            # Create temp instance to check feature types
            temp_instance = rec_class(None)  # type: ignore
            if feature_type in temp_instance.get_feature_types():
                results.append(rec_class)
        return results

    @classmethod
    def get_recognizer_info(cls, name: str) -> Optional[Dict[str, any]]:
        """
        Get detailed information about a recognizer.

        Args:
            name: Recognizer name

        Returns:
            Dictionary with recognizer information or None if not found
        """
        rec_class = cls.get(name)
        if not rec_class:
            return None

        # Create temp instance to get metadata
        temp_instance = rec_class(None)  # type: ignore

        return {
            'name': temp_instance.get_name(),
            'description': temp_instance.get_description(),
            'feature_types': [ft.value for ft in temp_instance.get_feature_types()],
            'class': rec_class.__name__,
            'module': rec_class.__module__
        }

    @classmethod
    def get_all_info(cls) -> List[Dict[str, any]]:
        """
        Get information about all registered recognizers.

        Returns:
            List of recognizer information dictionaries
        """
        info_list = []
        for name in cls.list_all():
            info = cls.get_recognizer_info(name)
            if info:
                info_list.append(info)
        return info_list

    @classmethod
    def clear(cls) -> None:
        """
        Clear all registered recognizers.
        Useful for testing.
        """
        cls._recognizers.clear()
        logger.info("Cleared all registered recognizers")

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """
        Check if a recognizer is registered.

        Args:
            name: Recognizer name

        Returns:
            True if registered
        """
        return name in cls._recognizers

    @classmethod
    def count(cls) -> int:
        """
        Get count of registered recognizers.

        Returns:
            Number of registered recognizers
        """
        return len(cls._recognizers)


def register_recognizer(cls: Type[BaseRecognizer]) -> Type[BaseRecognizer]:
    """
    Decorator for auto-registering recognizers.

    Usage:
        @register_recognizer
        class MyRecognizer(BaseRecognizer):
            ...

    Args:
        cls: Recognizer class to register

    Returns:
        The same class (unmodified)
    """
    RecognizerRegistry.register(cls)
    return cls
