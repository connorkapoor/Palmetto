"""
AAG Graph export API routes.
"""

import logging
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any

from app.storage.model_store import ModelStore

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

    # First check if C++ engine generated an aag.json
    cpp_aag_file = DATA_DIR / model_id / "output" / "aag.json"
    if cpp_aag_file.exists():
        logger.info(f"Loading graph from C++ engine: {cpp_aag_file}")
        try:
            with open(cpp_aag_file, 'r') as f:
                aag_data = json.load(f)
                return aag_data  # C++ engine already formats it correctly
        except Exception as e:
            logger.error(f"Failed to load C++ AAG: {e}")
            # Fall through to ModelStore

    # Fall back to Python-based graph from store
    graph = ModelStore.get_graph(model_id)
    if not graph:
        raise HTTPException(status_code=404, detail="Model not found")

    # Convert to visualization format
    nodes = []
    links = []

    # Color mapping for node types
    type_colors = {
        "vertex": "#4a90e2",  # Blue
        "edge": "#50c878",    # Green
        "face": "#f5a623",    # Orange
        "shell": "#bd10e0",   # Purple
        "solid": "#e74c3c",   # Red
    }

    # Build nodes
    for node_id, node in graph.nodes.items():
        node_type = node.topology_type.value

        # Extract relevant attributes for tooltip
        attrs = {}
        if node_type == "vertex":
            if 'x' in node.attributes:
                attrs['position'] = f"({node.attributes['x']:.2f}, {node.attributes['y']:.2f}, {node.attributes['z']:.2f})"
        elif node_type == "edge":
            if 'curve_type' in node.attributes:
                attrs['curve_type'] = str(node.attributes['curve_type'])
            if 'length' in node.attributes:
                attrs['length'] = f"{node.attributes['length']:.2f}"
        elif node_type == "face":
            if 'surface_type' in node.attributes:
                attrs['surface_type'] = str(node.attributes['surface_type'])
            if 'area' in node.attributes:
                attrs['area'] = f"{node.attributes['area']:.2f}"

        nodes.append({
            "id": node_id,
            "name": node_id,
            "group": node_type,
            "color": type_colors.get(node_type, "#888888"),
            "val": 5 if node_type == "face" else 3,  # Size based on importance
            "attributes": attrs
        })

    # Build links
    for edge_id, edge in graph.edges.items():
        links.append({
            "source": edge.source,
            "target": edge.target,
            "type": edge.relationship.value,
            "id": edge_id
        })

    stats = graph.get_statistics()

    logger.info(f"Graph export complete: {len(nodes)} nodes, {len(links)} links")

    return {
        "nodes": nodes,
        "links": links,
        "stats": stats
    }
