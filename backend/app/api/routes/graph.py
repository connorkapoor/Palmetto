"""
AAG Graph export API routes.
"""

import logging
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/graph", tags=["graph"])

# Data directory for C++ engine outputs
DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"


@router.get("/{model_id}")
async def get_graph(model_id: str):
    """
    Get the AAG graph structure for visualization.

    Args:
        model_id: Model identifier

    Returns:
        Graph data in format suitable for force-graph visualization:
        {
            nodes: [{id, name, group, type, ...}],
            links: [{source, target, type, ...}]
        }
    """
    logger.info(f"Getting graph for model {model_id}")

    # Load AAG from C++ engine output
    cpp_aag_file = DATA_DIR / model_id / "output" / "aag.json"
    if not cpp_aag_file.exists():
        raise HTTPException(status_code=404, detail=f"Model not found or not yet processed")

    logger.info(f"Loading graph from C++ engine: {cpp_aag_file}")
    try:
        with open(cpp_aag_file, 'r') as f:
            aag_data = json.load(f)
            return aag_data  # C++ engine already formats it correctly
    except Exception as e:
        logger.error(f"Failed to load C++ AAG: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load graph data: {str(e)}")
