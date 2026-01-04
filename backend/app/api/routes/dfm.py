"""
DFM (Design for Manufacturing) API routes.

Provides endpoints for automated manufacturing constraint checking.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
import json
import os
import logging

from app.dfm.manufacturing_rules import (
    check_dfm_compliance,
    get_rules_for_process,
    get_violation_summary
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dfm", tags=["DFM"])


@router.get("/{model_id}/check")
async def check_dfm(
    model_id: str,
    process: Optional[str] = Query(
        default="injection_molding",
        description="Manufacturing process: injection_molding, cnc_machining, or additive_manufacturing"
    ),
    include_warnings: bool = Query(
        default=True,
        description="Include warning-level violations"
    ),
    include_info: bool = Query(
        default=False,
        description="Include info-level violations"
    )
):
    """
    Run DFM compliance check on a model.

    Checks the model's AAG data against manufacturing rules for the specified process.

    Args:
        model_id: Model identifier
        process: Manufacturing process (injection_molding, cnc_machining, additive_manufacturing)
        include_warnings: Include warning-level violations in results
        include_info: Include info-level violations in results

    Returns:
        Dictionary with:
            - model_id: Model identifier
            - process: Manufacturing process checked
            - summary: Violation counts by severity
            - violations: List of violation details
    """
    # Construct path to AAG file
    aag_path = os.path.join("data", model_id, "output", "aag.json")

    # Check if file exists
    if not os.path.exists(aag_path):
        raise HTTPException(
            status_code=404,
            detail=f"Model not found or not analyzed. Expected AAG file at: {aag_path}"
        )

    # Load AAG data
    try:
        with open(aag_path, 'r') as f:
            aag_data = json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse AAG JSON: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to parse AAG data"
        )
    except Exception as e:
        logger.error(f"Error reading AAG file: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error reading AAG file: {str(e)}"
        )

    # Get rules for the specified manufacturing process
    rules = get_rules_for_process(process)

    # Run DFM compliance check
    violations = check_dfm_compliance(aag_data, rules, entity_types=["face"])

    # Filter violations by severity
    filtered_violations = []
    for v in violations:
        if v["severity"] == "error":
            filtered_violations.append(v)
        elif v["severity"] == "warning" and include_warnings:
            filtered_violations.append(v)
        elif v["severity"] == "info" and include_info:
            filtered_violations.append(v)

    # Generate summary
    summary = get_violation_summary(filtered_violations)

    logger.info(f"DFM check for {model_id} ({process}): {summary['total']} violations found")

    return {
        "model_id": model_id,
        "process": process,
        "summary": summary,
        "violations": filtered_violations
    }


@router.get("/{model_id}/summary")
async def get_dfm_summary(
    model_id: str,
    process: Optional[str] = Query(
        default="injection_molding",
        description="Manufacturing process"
    )
):
    """
    Get a quick summary of DFM violations without full details.

    Args:
        model_id: Model identifier
        process: Manufacturing process

    Returns:
        Dictionary with violation counts by severity and rule
    """
    # Construct path to AAG file
    aag_path = os.path.join("data", model_id, "output", "aag.json")

    if not os.path.exists(aag_path):
        raise HTTPException(
            status_code=404,
            detail="Model not found or not analyzed"
        )

    # Load AAG data
    try:
        with open(aag_path, 'r') as f:
            aag_data = json.load(f)
    except Exception as e:
        logger.error(f"Error reading AAG file: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error reading AAG file: {str(e)}"
        )

    # Get rules and run check
    rules = get_rules_for_process(process)
    violations = check_dfm_compliance(aag_data, rules, entity_types=["face"])

    # Generate summary
    summary = get_violation_summary(violations)

    return {
        "model_id": model_id,
        "process": process,
        **summary
    }


@router.get("/processes")
async def list_processes():
    """
    List available manufacturing processes and their rules.

    Returns:
        Dictionary of process names and their rule counts
    """
    processes = {
        "injection_molding": {
            "name": "Injection Molding",
            "description": "Thermoplastic injection molding process",
            "rule_count": len(get_rules_for_process("injection_molding"))
        },
        "cnc_machining": {
            "name": "CNC Machining",
            "description": "Subtractive manufacturing with CNC mills",
            "rule_count": len(get_rules_for_process("cnc_machining"))
        },
        "additive_manufacturing": {
            "name": "Additive Manufacturing",
            "description": "3D printing (FDM, SLA, SLS)",
            "rule_count": len(get_rules_for_process("additive_manufacturing"))
        }
    }

    return processes
