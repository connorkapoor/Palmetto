"""
Taxonomy Mapper - Maps MFCAD feature labels to Palmetto FeatureTypes.

The MFCAD dataset has 16 feature types, and Palmetto has its own FeatureType enum.
This mapper provides bidirectional translation and property extraction.
"""

from typing import Dict, Tuple, Optional
from app.recognizers.base import FeatureType


class TaxonomyMapper:
    """
    Maps MFCAD feature taxonomy to Palmetto FeatureType enum.

    Design decisions (per user requirements):
    - New FeatureTypes added: STEP_THROUGH, STEP_BLIND, PASSAGE
    - Shape stored as property: {"shape": "rectangular"}
    - Stock (label 15) treated as negative class (None)
    """

    # MFCAD label index → (Palmetto FeatureType, properties dict)
    MFCAD_TO_PALMETTO: Dict[int, Optional[Tuple[FeatureType, Dict[str, str]]]] = {
        # Slots
        0: (FeatureType.CAVITY_SLOT, {"shape": "rectangular"}),        # rectangular_through_slot
        1: (FeatureType.CAVITY_SLOT, {"shape": "triangular"}),         # triangular_through_slot
        10: (FeatureType.CAVITY_SLOT, {"shape": "rectangular"}),       # rectangular_blind_slot

        # Passages
        2: (FeatureType.PASSAGE, {"shape": "rectangular"}),            # rectangular_passage
        3: (FeatureType.PASSAGE, {"shape": "triangular"}),             # triangular_passage
        4: (FeatureType.PASSAGE, {"shape": "hexagonal"}),              # 6sides_passage

        # Through Steps
        5: (FeatureType.STEP_THROUGH, {"shape": "rectangular"}),       # rectangular_through_step
        6: (FeatureType.STEP_THROUGH, {"shape": "rectangular"}),       # 2sides_through_step
        7: (FeatureType.STEP_THROUGH, {"shape": "slanted"}),           # slanted_through_step

        # Blind Steps
        8: (FeatureType.STEP_BLIND, {"shape": "rectangular"}),         # rectangular_blind_step
        9: (FeatureType.STEP_BLIND, {"shape": "triangular"}),          # triangular_blind_step

        # Pockets
        11: (FeatureType.CAVITY_POCKET, {"shape": "rectangular"}),     # rectangular_pocket
        12: (FeatureType.CAVITY_POCKET, {"shape": "triangular"}),      # triangular_pocket
        13: (FeatureType.CAVITY_POCKET, {"shape": "hexagonal"}),       # 6sides_pocket

        # Chamfer
        14: (FeatureType.CHAMFER, {}),                                 # chamfer

        # Stock (base material) - negative class
        15: None  # Not a feature
    }

    # Reverse mapping: Palmetto FeatureType → MFCAD label indices
    PALMETTO_TO_MFCAD: Dict[FeatureType, list] = {
        FeatureType.CAVITY_SLOT: [0, 1, 10],
        FeatureType.PASSAGE: [2, 3, 4],
        FeatureType.STEP_THROUGH: [5, 6, 7],
        FeatureType.STEP_BLIND: [8, 9],
        FeatureType.CAVITY_POCKET: [11, 12, 13],
        FeatureType.CHAMFER: [14],
    }

    # MFCAD feature names
    MFCAD_NAMES = [
        'rectangular_through_slot',   # 0
        'triangular_through_slot',    # 1
        'rectangular_passage',        # 2
        'triangular_passage',         # 3
        '6sides_passage',             # 4
        'rectangular_through_step',   # 5
        '2sides_through_step',        # 6
        'slanted_through_step',       # 7
        'rectangular_blind_step',     # 8
        'triangular_blind_step',      # 9
        'rectangular_blind_slot',     # 10
        'rectangular_pocket',         # 11
        'triangular_pocket',          # 12
        '6sides_pocket',              # 13
        'chamfer',                    # 14
        'stock'                       # 15
    ]

    @classmethod
    def mfcad_to_palmetto(cls, mfcad_label: int) -> Optional[Tuple[FeatureType, Dict[str, str]]]:
        """
        Convert MFCAD label index to Palmetto FeatureType and properties.

        Args:
            mfcad_label: MFCAD feature label index (0-15)

        Returns:
            Tuple of (FeatureType, properties) or None for stock
        """
        return cls.MFCAD_TO_PALMETTO.get(mfcad_label)

    @classmethod
    def get_mfcad_name(cls, mfcad_label: int) -> str:
        """Get human-readable name for MFCAD label."""
        if 0 <= mfcad_label < len(cls.MFCAD_NAMES):
            return cls.MFCAD_NAMES[mfcad_label]
        return "unknown"

    @classmethod
    def is_stock(cls, mfcad_label: int) -> bool:
        """Check if label represents stock/base material."""
        return mfcad_label == 15

    @classmethod
    def get_all_palmetto_types(cls) -> list[FeatureType]:
        """Get list of all Palmetto FeatureTypes used in MFCAD mapping."""
        return list(cls.PALMETTO_TO_MFCAD.keys())
