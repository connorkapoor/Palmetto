"""
AAG (Attributed Adjacency Graph) data access routes.

Provides endpoints for accessing complete AAG data including all geometric
attributes for vertices, edges, faces, and their relationships.
"""

import json
import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/aag", tags=["aag"])

# Data directory for loading AAG files
DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"


class AAGNode(BaseModel):
    """AAG node representing a topological entity"""
    id: str
    group: str  # vertex, edge, face, shell
    label: Optional[str] = None
    attributes: Dict[str, Any] = {}


class AAGLink(BaseModel):
    """AAG link representing adjacency relationship"""
    source: str
    target: str
    attributes: Dict[str, Any] = {}


class AAGData(BaseModel):
    """Complete AAG data structure"""
    nodes: List[AAGNode]
    links: List[AAGLink]
    metadata: Dict[str, Any] = {}


@router.get("/{model_id}/full", response_model=AAGData, summary="Get complete AAG data")
async def get_full_aag(model_id: str):
    """
    Get complete AAG (Attributed Adjacency Graph) data for a model.

    Returns all topological entities (vertices, edges, faces, shells) with
    their geometric attributes and adjacency relationships.

    This endpoint provides the complete AAG data needed for:
    - Query execution
    - Autocomplete suggestions
    - Geometric analysis
    - Relationship queries

    Args:
        model_id: Model identifier

    Returns:
        AAGData with all nodes, links, and metadata

    Node attributes by type:
        - vertex: x, y, z coordinates
        - edge: curve_type, length, radius, points (discretized)
        - face: area, surface_type, normal, radius
        - shell: volume (if available)

    Link attributes:
        - dihedral_angle: Signed angle between adjacent faces
        - convex: Boolean flag for convex edges
        - concave: Boolean flag for concave edges
        - smooth: Boolean flag for smooth edges
    """
    logger.info(f"AAG data request for model {model_id}")

    # Get AAG file path
    aag_file = DATA_DIR / model_id / "output" / "aag.json"

    if not aag_file.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Model {model_id} not found or not yet processed. Upload and process a STEP file first."
        )

    try:
        # Load AAG data
        with open(aag_file, 'r') as f:
            aag_json = json.load(f)

        # Extract nodes and links
        nodes = aag_json.get("nodes", [])
        links = aag_json.get("links", [])

        # Build metadata
        metadata = {
            "model_id": model_id,
            "total_nodes": len(nodes),
            "total_links": len(links),
            "node_counts": {
                "vertices": len([n for n in nodes if n.get("group") == "vertex"]),
                "edges": len([n for n in nodes if n.get("group") == "edge"]),
                "faces": len([n for n in nodes if n.get("group") == "face"]),
                "shells": len([n for n in nodes if n.get("group") == "shell"])
            }
        }

        logger.info(f"Returning AAG with {len(nodes)} nodes and {len(links)} links")

        return AAGData(
            nodes=nodes,
            links=links,
            metadata=metadata
        )

    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        raise HTTPException(
            status_code=404,
            detail=f"AAG data not found for model {model_id}"
        )

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in AAG file: {e}")
        raise HTTPException(
            status_code=500,
            detail="Invalid AAG data format"
        )

    except Exception as e:
        logger.error(f"Failed to load AAG data: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load AAG data: {str(e)}"
        )


@router.get("/{model_id}/nodes/{entity_type}", summary="Get nodes by entity type")
async def get_nodes_by_type(model_id: str, entity_type: str):
    """
    Get all nodes of a specific entity type.

    Args:
        model_id: Model identifier
        entity_type: Entity type (vertex, edge, face, shell)

    Returns:
        List of nodes matching the entity type
    """
    # Validate entity type
    valid_types = {"vertex", "edge", "face", "shell"}
    if entity_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid entity type. Must be one of: {', '.join(valid_types)}"
        )

    # Get AAG file path
    aag_file = DATA_DIR / model_id / "output" / "aag.json"

    if not aag_file.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Model {model_id} not found"
        )

    try:
        with open(aag_file, 'r') as f:
            aag_json = json.load(f)

        # Filter nodes by type
        nodes = [n for n in aag_json.get("nodes", []) if n.get("group") == entity_type]

        return {
            "model_id": model_id,
            "entity_type": entity_type,
            "nodes": nodes,
            "count": len(nodes)
        }

    except Exception as e:
        logger.error(f"Failed to get nodes: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get nodes: {str(e)}"
        )


@router.get("/{model_id}/statistics", summary="Get AAG statistics")
async def get_aag_statistics(model_id: str):
    """
    Get statistical summary of AAG data.

    Returns counts, attribute ranges, and other useful statistics.

    Args:
        model_id: Model identifier

    Returns:
        Statistical summary of AAG data
    """
    aag_file = DATA_DIR / model_id / "output" / "aag.json"

    if not aag_file.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Model {model_id} not found"
        )

    try:
        with open(aag_file, 'r') as f:
            aag_json = json.load(f)

        nodes = aag_json.get("nodes", [])
        links = aag_json.get("links", [])

        # Group nodes by type
        faces = [n for n in nodes if n.get("group") == "face"]
        edges = [n for n in nodes if n.get("group") == "edge"]
        vertices = [n for n in nodes if n.get("group") == "vertex"]
        shells = [n for n in nodes if n.get("group") == "shell"]

        # Calculate face statistics
        face_areas = [n.get("attributes", {}).get("area", 0) for n in faces if "area" in n.get("attributes", {})]
        face_types = {}
        for f in faces:
            surf_type = f.get("attributes", {}).get("surface_type", "unknown")
            face_types[surf_type] = face_types.get(surf_type, 0) + 1

        # Calculate edge statistics
        edge_lengths = [n.get("attributes", {}).get("length", 0) for n in edges if "length" in n.get("attributes", {})]
        edge_types = {}
        for e in edges:
            curve_type = e.get("attributes", {}).get("curve_type", "unknown")
            edge_types[curve_type] = edge_types.get(curve_type, 0) + 1

        statistics = {
            "model_id": model_id,
            "total_nodes": len(nodes),
            "total_links": len(links),
            "node_counts": {
                "vertices": len(vertices),
                "edges": len(edges),
                "faces": len(faces),
                "shells": len(shells)
            },
            "face_statistics": {
                "total": len(faces),
                "types": face_types,
                "area_range": {
                    "min": min(face_areas) if face_areas else 0,
                    "max": max(face_areas) if face_areas else 0,
                    "avg": sum(face_areas) / len(face_areas) if face_areas else 0
                }
            },
            "edge_statistics": {
                "total": len(edges),
                "types": edge_types,
                "length_range": {
                    "min": min(edge_lengths) if edge_lengths else 0,
                    "max": max(edge_lengths) if edge_lengths else 0,
                    "avg": sum(edge_lengths) / len(edge_lengths) if edge_lengths else 0
                }
            }
        }

        return statistics

    except Exception as e:
        logger.error(f"Failed to get statistics: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get statistics: {str(e)}"
        )
