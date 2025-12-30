"""
MFCAD Dataset Integration and Validation Framework

This module provides tools for loading the MFCAD labeled dataset,
validating feature recognizers against ground truth, and analyzing
recognition accuracy.
"""

from .mfcad_loader import MFCADLoader, MFCADModel
from .taxonomy_mapper import TaxonomyMapper
from .validation import RecognizerValidator, ValidationResult
from .metrics import MetricsCalculator, MetricsReport

__all__ = [
    'MFCADLoader',
    'MFCADModel',
    'TaxonomyMapper',
    'RecognizerValidator',
    'ValidationResult',
    'MetricsCalculator',
    'MetricsReport',
]
