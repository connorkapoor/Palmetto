"""
Manufacturing rules engine for DFM (Design for Manufacturing) checks.

Provides automated detection of manufacturing constraint violations
including wall thickness, feature size, and stress concentration issues.
"""

from dataclasses import dataclass
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


@dataclass
class ManufacturingRule:
    """
    A single manufacturing constraint rule.

    Attributes:
        name: Unique identifier for the rule
        attribute: AAG attribute to check (e.g., "local_thickness", "radius")
        operator: Comparison operator ('lt', 'gt', 'eq')
        threshold: Threshold value for comparison
        severity: 'error' (critical), 'warning' (important), or 'info'
        message: Human-readable description of the violation
    """
    name: str
    attribute: str
    operator: str  # 'lt', 'gt', 'eq'
    threshold: float
    severity: str  # 'error', 'warning', 'info'
    message: str


# Default rules for injection molding
INJECTION_MOLDING_RULES = [
    ManufacturingRule(
        name="minimum_wall_thickness",
        attribute="local_thickness",
        operator="lt",
        threshold=0.8,  # mm
        severity="error",
        message="Wall thickness below 0.8mm may cause flow issues during injection molding"
    ),
    ManufacturingRule(
        name="maximum_wall_thickness",
        attribute="local_thickness",
        operator="gt",
        threshold=10.0,  # mm
        severity="warning",
        message="Wall thickness above 10mm may cause sink marks and long cycle times"
    ),
    ManufacturingRule(
        name="thickness_variance_uniformity",
        attribute="thickness_variance",
        operator="gt",
        threshold=0.3,  # standard deviation
        severity="warning",
        message="Non-uniform wall thickness (variance > 0.3) may cause warping and uneven cooling"
    ),
    ManufacturingRule(
        name="high_thickness_variance",
        attribute="thickness_variance",
        operator="gt",
        threshold=0.6,  # standard deviation
        severity="error",
        message="Severe wall thickness variation (variance > 0.6) will likely cause defects"
    ),
    ManufacturingRule(
        name="insufficient_draft_angle",
        attribute="draft_angle",
        operator="lt",
        threshold=1.0,  # degrees
        severity="error",
        message="Draft angle < 1° may prevent part ejection from mold"
    ),
    ManufacturingRule(
        name="marginal_draft_angle",
        attribute="draft_angle",
        operator="lt",
        threshold=2.0,  # degrees
        severity="warning",
        message="Draft angle < 2° may cause ejection difficulty or surface damage"
    ),
    ManufacturingRule(
        name="hard_undercut_detected",
        attribute="has_undercut",
        operator="eq",
        threshold=True,
        severity="error",
        message="Undercut requires side action, lifter, or manual demolding"
    ),
    ManufacturingRule(
        name="true_undercut_detected",
        attribute="is_undercut",
        operator="eq",
        threshold=True,
        severity="error",
        message="True undercut detected - face is blocked and cannot be demolded straight"
    ),
    ManufacturingRule(
        name="side_action_required",
        attribute="requires_side_action",
        operator="eq",
        threshold=True,
        severity="error",
        message="Complex undercut requires side action, lifter, or manual demolding (increases tooling cost)"
    ),
    ManufacturingRule(
        name="low_molding_accessibility",
        attribute="molding_accessibility_score",
        operator="lt",
        threshold=0.3,
        severity="warning",
        message="Low molding accessibility score - may have demolding challenges"
    ),
    ManufacturingRule(
        name="minimum_fillet_radius",
        attribute="radius",
        operator="lt",
        threshold=0.5,  # mm
        severity="warning",
        message="Fillet radius below 0.5mm may cause stress concentration and mold wear"
    ),
    ManufacturingRule(
        name="very_small_feature",
        attribute="area",
        operator="lt",
        threshold=1.0,  # mm²
        severity="warning",
        message="Very small face (< 1mm²) may be difficult to manufacture accurately"
    ),
]

# Rules for CNC machining
CNC_MACHINING_RULES = [
    ManufacturingRule(
        name="minimum_internal_radius",
        attribute="radius",
        operator="lt",
        threshold=0.5,  # mm - typical 1mm endmill radius
        severity="error",
        message="Internal radius below 0.5mm cannot be machined with standard endmills"
    ),
    ManufacturingRule(
        name="small_internal_radius",
        attribute="radius",
        operator="lt",
        threshold=1.0,  # mm
        severity="warning",
        message="Internal radius below 1mm requires small endmills and increases machining time"
    ),
    ManufacturingRule(
        name="minimum_wall_thickness",
        attribute="local_thickness",
        operator="lt",
        threshold=0.8,  # mm
        severity="error",
        message="Wall thickness below 0.8mm may cause deflection during machining"
    ),
    ManufacturingRule(
        name="very_thin_wall",
        attribute="local_thickness",
        operator="lt",
        threshold=1.5,  # mm
        severity="warning",
        message="Thin walls below 1.5mm may vibrate during machining, causing poor surface finish"
    ),
    ManufacturingRule(
        name="high_stress_concentration",
        attribute="stress_concentration",
        operator="gt",
        threshold=0.8,  # 0-1 normalized
        severity="warning",
        message="High stress concentration - consider increasing fillet radius or wall thickness"
    ),
    ManufacturingRule(
        name="very_small_feature",
        attribute="area",
        operator="lt",
        threshold=0.5,  # mm²
        severity="warning",
        message="Very small feature may require micro-machining tools"
    ),
    ManufacturingRule(
        name="cnc_inaccessible_face",
        attribute="is_accessible_cnc",
        operator="eq",
        threshold=False,
        severity="error",
        message="Face cannot be reached by cutting tool from any standard direction (+/-X, +/-Y, +/-Z)"
    ),
    ManufacturingRule(
        name="low_cnc_accessibility",
        attribute="cnc_accessibility_score",
        operator="lt",
        threshold=0.3,
        severity="warning",
        message="Low CNC accessibility score - limited tool access, may require special fixturing"
    ),
    ManufacturingRule(
        name="deep_narrow_pocket",
        attribute="is_deep_pocket",
        operator="eq",
        threshold=True,
        severity="warning",
        message="Deep pocket (aspect ratio > 2.0) requires long-reach tooling and may have chip evacuation issues"
    ),
    ManufacturingRule(
        name="extreme_aspect_ratio_pocket",
        attribute="pocket_aspect_ratio",
        operator="gt",
        threshold=4.0,
        severity="error",
        message="Extreme pocket aspect ratio (> 4.0) - very difficult or impossible to machine with standard tools"
    ),
    ManufacturingRule(
        name="narrow_pocket_opening",
        attribute="is_narrow_pocket",
        operator="eq",
        threshold=True,
        severity="warning",
        message="Narrow pocket opening (< 5mm) limits tool size and may require specialized tooling"
    ),
]

# Rules for 3D printing (Additive Manufacturing)
ADDITIVE_MANUFACTURING_RULES = [
    ManufacturingRule(
        name="minimum_wall_thickness",
        attribute="local_thickness",
        operator="lt",
        threshold=0.4,  # mm - typical nozzle width
        severity="error",
        message="Wall thickness below 0.4mm cannot be reliably printed (less than nozzle width)"
    ),
    ManufacturingRule(
        name="very_thin_feature",
        attribute="local_thickness",
        operator="lt",
        threshold=1.0,  # mm
        severity="warning",
        message="Thin features below 1mm may be fragile and difficult to clean"
    ),
    ManufacturingRule(
        name="overhang_requires_support",
        attribute="overhang_angle",
        operator="gt",
        threshold=45.0,  # degrees from horizontal
        severity="warning",
        message="Overhang > 45° requires support structures (increases material waste and post-processing)"
    ),
    ManufacturingRule(
        name="extreme_overhang",
        attribute="overhang_angle",
        operator="gt",
        threshold=70.0,  # degrees
        severity="error",
        message="Overhang > 70° will likely fail to print without extensive supports"
    ),
    ManufacturingRule(
        name="small_feature_detail",
        attribute="area",
        operator="lt",
        threshold=0.5,  # mm²
        severity="warning",
        message="Very small features may not print accurately due to layer resolution"
    ),
]

# Rules for sheet metal fabrication
SHEET_METAL_RULES = [
    ManufacturingRule(
        name="minimum_bend_radius",
        attribute="radius",
        operator="lt",
        threshold=1.5,  # mm - 1.5x typical sheet thickness
        severity="error",
        message="Bend radius < 1.5mm may cause cracking or material failure"
    ),
    ManufacturingRule(
        name="small_bend_radius",
        attribute="radius",
        operator="lt",
        threshold=3.0,  # mm
        severity="warning",
        message="Bend radius < 3mm may require specialized tooling"
    ),
    ManufacturingRule(
        name="minimum_hole_edge_distance",
        attribute="local_thickness",
        operator="lt",
        threshold=2.0,  # mm - hole to edge distance
        severity="warning",
        message="Features too close to edges may cause deformation during bending"
    ),
    ManufacturingRule(
        name="very_thin_sheet",
        attribute="local_thickness",
        operator="lt",
        threshold=0.5,  # mm
        severity="error",
        message="Sheet thickness below 0.5mm is difficult to handle and may tear"
    ),
    ManufacturingRule(
        name="very_thick_sheet",
        attribute="local_thickness",
        operator="gt",
        threshold=6.0,  # mm
        severity="warning",
        message="Sheet thickness above 6mm requires heavy-duty press brake and tooling"
    ),
]

# Rules for investment casting
INVESTMENT_CASTING_RULES = [
    ManufacturingRule(
        name="minimum_wall_thickness",
        attribute="local_thickness",
        operator="lt",
        threshold=2.0,  # mm
        severity="error",
        message="Wall thickness below 2mm may not fill properly during casting"
    ),
    ManufacturingRule(
        name="thin_wall_casting",
        attribute="local_thickness",
        operator="lt",
        threshold=3.0,  # mm
        severity="warning",
        message="Wall thickness below 3mm may have porosity or incomplete fill"
    ),
    ManufacturingRule(
        name="sharp_internal_corner",
        attribute="radius",
        operator="lt",
        threshold=1.0,  # mm
        severity="error",
        message="Internal corner radius < 1mm causes stress concentration and hot spots"
    ),
    ManufacturingRule(
        name="small_internal_radius",
        attribute="radius",
        operator="lt",
        threshold=2.0,  # mm
        severity="warning",
        message="Internal radius < 2mm may cause localized cooling issues"
    ),
    ManufacturingRule(
        name="thickness_variance",
        attribute="thickness_variance",
        operator="gt",
        threshold=0.4,  # standard deviation
        severity="warning",
        message="Non-uniform wall thickness may cause uneven cooling and porosity"
    ),
    ManufacturingRule(
        name="undercut_requires_core",
        attribute="has_undercut",
        operator="eq",
        threshold=True,
        severity="error",
        message="Undercut requires complex coring or multi-part mold"
    ),
]


def check_dfm_compliance(
    aag_data: Dict[str, Any],
    rules: List[ManufacturingRule],
    entity_types: List[str] = ["face"]
) -> List[Dict[str, Any]]:
    """
    Check AAG data against manufacturing rules.

    Args:
        aag_data: AAG JSON data with nodes and attributes
        rules: List of ManufacturingRule objects to check
        entity_types: List of entity types to check (default: ["face"])

    Returns:
        List of violation dictionaries with:
            - entity_id: ID of the violating entity
            - entity_type: Type of entity (face, edge, etc.)
            - rule: Rule name
            - severity: 'error', 'warning', or 'info'
            - message: Human-readable description
            - value: Actual measured value
            - threshold: Expected threshold
    """
    violations = []
    checked_count = 0

    nodes = aag_data.get("nodes", [])

    for node in nodes:
        node_type = node.get("group", "")

        # Skip if not in requested entity types
        if node_type not in entity_types:
            continue

        entity_id = node.get("id", "unknown")
        attributes = node.get("attributes", {})

        checked_count += 1

        for rule in rules:
            # Skip if attribute doesn't exist on this node
            if rule.attribute not in attributes:
                continue

            value = attributes[rule.attribute]

            # Skip invalid/null values
            if value is None or (isinstance(value, (int, float)) and value < 0):
                continue

            # Check violation based on operator
            is_violation = False

            if rule.operator == "lt" and value < rule.threshold:
                is_violation = True
            elif rule.operator == "gt" and value > rule.threshold:
                is_violation = True
            elif rule.operator == "eq" and value == rule.threshold:
                is_violation = True
            elif rule.operator == "lte" and value <= rule.threshold:
                is_violation = True
            elif rule.operator == "gte" and value >= rule.threshold:
                is_violation = True

            if is_violation:
                violations.append({
                    "entity_id": entity_id,
                    "entity_type": node_type,
                    "rule": rule.name,
                    "severity": rule.severity,
                    "message": rule.message,
                    "value": round(value, 3) if isinstance(value, float) else value,
                    "threshold": rule.threshold,
                    "attribute": rule.attribute
                })

    logger.info(f"DFM check complete: {checked_count} entities checked, {len(violations)} violations found")

    return violations


def get_rules_for_process(process: str = "injection_molding") -> List[ManufacturingRule]:
    """
    Get manufacturing rules for a specific manufacturing process.

    Args:
        process: Manufacturing process name
            - "injection_molding" (default)
            - "cnc_machining"
            - "additive_manufacturing" or "3d_printing"
            - "sheet_metal"
            - "investment_casting"

    Returns:
        List of ManufacturingRule objects
    """
    process_lower = process.lower().replace("-", "_").replace(" ", "_")

    if process_lower in ["injection_molding", "injection", "molding"]:
        return INJECTION_MOLDING_RULES
    elif process_lower in ["cnc_machining", "cnc", "machining", "milling"]:
        return CNC_MACHINING_RULES
    elif process_lower in ["additive_manufacturing", "3d_printing", "fdm", "sla", "sls", "additive"]:
        return ADDITIVE_MANUFACTURING_RULES
    elif process_lower in ["sheet_metal", "sheet", "metal", "bending"]:
        return SHEET_METAL_RULES
    elif process_lower in ["investment_casting", "casting", "investment"]:
        return INVESTMENT_CASTING_RULES
    else:
        logger.warning(f"Unknown manufacturing process '{process}', defaulting to injection molding")
        return INJECTION_MOLDING_RULES


def get_violation_summary(violations: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate a summary of DFM violations.

    Args:
        violations: List of violation dictionaries from check_dfm_compliance

    Returns:
        Dictionary with summary statistics:
            - total: Total violation count
            - errors: Critical violations count
            - warnings: Warning violations count
            - info: Info violations count
            - by_rule: Count per rule name
            - by_entity_type: Count per entity type
    """
    errors = [v for v in violations if v["severity"] == "error"]
    warnings = [v for v in violations if v["severity"] == "warning"]
    info = [v for v in violations if v["severity"] == "info"]

    # Count by rule
    by_rule = {}
    for v in violations:
        rule_name = v["rule"]
        by_rule[rule_name] = by_rule.get(rule_name, 0) + 1

    # Count by entity type
    by_entity_type = {}
    for v in violations:
        entity_type = v["entity_type"]
        by_entity_type[entity_type] = by_entity_type.get(entity_type, 0) + 1

    return {
        "total": len(violations),
        "errors": len(errors),
        "warnings": len(warnings),
        "info": len(info),
        "by_rule": by_rule,
        "by_entity_type": by_entity_type
    }
