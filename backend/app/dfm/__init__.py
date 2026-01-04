"""
DFM (Design for Manufacturing) package.

Provides manufacturing constraint checking and violation detection.
"""

from .manufacturing_rules import (
    ManufacturingRule,
    INJECTION_MOLDING_RULES,
    check_dfm_compliance
)

__all__ = [
    "ManufacturingRule",
    "INJECTION_MOLDING_RULES",
    "check_dfm_compliance"
]
