"""
Query API routes for natural language geometric queries.

Provides endpoints for executing natural language queries against AAG data.
"""

import json
import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional, Any

from app.query.query_engine import QueryEngine, QueryResult as EngineQueryResult
from app.query.query_parser import QueryParser

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/query", tags=["query"])

# Data directory for loading AAG files
DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"


class QueryRequest(BaseModel):
    """Request to execute a natural language query"""
    model_id: str
    query: str


class QueryResponse(BaseModel):
    """Response from query execution"""
    model_id: str
    query: str
    structured_query: Dict[str, Any]
    matching_ids: List[str]
    total_matches: int
    entity_type: str
    execution_time_ms: float
    entities: Optional[List[Dict[str, Any]]] = None
    success: bool = True
    error: Optional[str] = None


# Initialize parser (singleton)
_query_parser = None


def get_query_parser() -> QueryParser:
    """Get or create QueryParser instance"""
    global _query_parser
    if _query_parser is None:
        _query_parser = QueryParser()
    return _query_parser


@router.post("/execute", response_model=QueryResponse, summary="Execute natural language query")
async def execute_query(request: QueryRequest):
    """
    Execute a natural language query against AAG data.

    This endpoint:
    1. Loads AAG data for the specified model
    2. Parses the natural language query using Claude API
    3. Executes the structured query against AAG nodes
    4. Returns matching entity IDs and statistics

    Args:
        request: QueryRequest with model_id and natural language query

    Returns:
        QueryResponse with matching entities and execution details

    Example queries:
        - "show me all faces with area 20mm²"
        - "find the largest face"
        - "show planar faces"
        - "find circular edges with radius 5mm"
    """
    logger.info(f"Query request for model {request.model_id}: '{request.query}'")

    # Get AAG file path
    aag_file = DATA_DIR / request.model_id / "output" / "aag.json"

    if not aag_file.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Model {request.model_id} not found or not yet processed. Upload and process a STEP file first."
        )

    try:
        # Load AAG data
        with open(aag_file, 'r') as f:
            aag_data = json.load(f)

        logger.info(f"Loaded AAG with {len(aag_data.get('nodes', []))} nodes")

        # Parse natural language query
        parser = get_query_parser()
        structured_query = parser.parse(request.query)

        logger.info(f"Structured query: {structured_query.entity_type}, {len(structured_query.predicates)} predicates")

        # Execute query
        engine = QueryEngine(aag_data)
        result = engine.execute(structured_query)

        # Convert structured query to dict for response
        structured_query_dict = {
            "entity_type": structured_query.entity_type,
            "predicates": [
                {
                    "attribute": p.attribute,
                    "operator": p.operator.value,
                    "value": p.value,
                    "tolerance": p.tolerance
                }
                for p in structured_query.predicates
            ],
            "sort_by": structured_query.sort_by,
            "order": structured_query.order,
            "limit": structured_query.limit
        }

        return QueryResponse(
            model_id=request.model_id,
            query=request.query,
            structured_query=structured_query_dict,
            matching_ids=result.matching_ids,
            total_matches=result.total_matches,
            entity_type=result.entity_type,
            execution_time_ms=result.execution_time_ms,
            entities=result.entities,
            success=True
        )

    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        raise HTTPException(
            status_code=404,
            detail=f"AAG data not found for model {request.model_id}"
        )

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in AAG file: {e}")
        raise HTTPException(
            status_code=500,
            detail="Invalid AAG data format"
        )

    except Exception as e:
        logger.error(f"Query execution failed: {e}", exc_info=True)
        return QueryResponse(
            model_id=request.model_id,
            query=request.query,
            structured_query={},
            matching_ids=[],
            total_matches=0,
            entity_type="",
            execution_time_ms=0.0,
            success=False,
            error=str(e)
        )


@router.get("/schema/{model_id}", summary="Get AAG schema for a model")
async def get_aag_schema(model_id: str):
    """
    Get the AAG schema for autocomplete and validation.

    Returns available entity types, attributes, and sample values.

    Args:
        model_id: Model identifier

    Returns:
        Schema information
    """
    aag_file = DATA_DIR / model_id / "output" / "aag.json"

    if not aag_file.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Model {request.model_id} not found"
        )

    try:
        with open(aag_file, 'r') as f:
            aag_data = json.load(f)

        # Extract schema from AAG data
        schema = {
            "entity_types": ["vertex", "edge", "face", "shell"],
            "attributes": {
                "face": {
                    "area": {"type": "number", "unit": "mm²"},
                    "surface_type": {
                        "type": "enum",
                        "values": ["plane", "cylinder", "cone", "sphere", "torus", "bspline"]
                    },
                    "normal": {"type": "vector3"},
                    "radius": {"type": "number", "unit": "mm"}
                },
                "edge": {
                    "curve_type": {
                        "type": "enum",
                        "values": ["line", "circle", "ellipse", "hyperbola", "parabola", "bezier", "bspline"]
                    },
                    "length": {"type": "number", "unit": "mm"},
                    "radius": {"type": "number", "unit": "mm"}
                },
                "vertex": {
                    "x": {"type": "number", "unit": "mm"},
                    "y": {"type": "number", "unit": "mm"},
                    "z": {"type": "number", "unit": "mm"}
                },
                "shell": {}
            },
            "operators": ["eq", "ne", "gt", "lt", "gte", "lte", "in_range", "contains", "in"],
            "statistics": {
                "total_nodes": len(aag_data.get("nodes", [])),
                "vertices": len([n for n in aag_data.get("nodes", []) if n.get("group") == "vertex"]),
                "edges": len([n for n in aag_data.get("nodes", []) if n.get("group") == "edge"]),
                "faces": len([n for n in aag_data.get("nodes", []) if n.get("group") == "face"]),
                "shells": len([n for n in aag_data.get("nodes", []) if n.get("group") == "shell"])
            }
        }

        return schema

    except Exception as e:
        logger.error(f"Failed to get schema: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get schema: {str(e)}")


@router.get("/examples", summary="Get example queries")
async def get_example_queries():
    """
    Get example queries for user reference.

    Returns:
        List of example queries with descriptions
    """
    examples = [
        {
            "query": "show me all faces with area 20mm²",
            "description": "Find faces with specific area (approximate match)",
            "category": "Face Queries"
        },
        {
            "query": "find the largest face",
            "description": "Find the face with maximum area",
            "category": "Face Queries"
        },
        {
            "query": "show planar faces",
            "description": "Find all planar (flat) faces",
            "category": "Face Queries"
        },
        {
            "query": "find cylindrical faces",
            "description": "Find all cylindrical faces",
            "category": "Face Queries"
        },
        {
            "query": "find fillets",
            "description": "Find fillet surfaces (cylindrical faces with arc edges)",
            "category": "Face Queries"
        },
        {
            "query": "find holes",
            "description": "Find hole surfaces (cylindrical faces with full circle edges)",
            "category": "Face Queries"
        },
        {
            "query": "faces with area greater than 50mm²",
            "description": "Find faces larger than threshold",
            "category": "Face Queries"
        },
        {
            "query": "find circular edges",
            "description": "Find all circular edges (arcs and circles)",
            "category": "Edge Queries"
        },
        {
            "query": "edges with radius 5mm",
            "description": "Find circular edges with specific radius",
            "category": "Edge Queries"
        },
        {
            "query": "find all line edges",
            "description": "Find all straight line edges",
            "category": "Edge Queries"
        },
        {
            "query": "smallest edge",
            "description": "Find the shortest edge",
            "category": "Edge Queries"
        },
        {
            "query": "edges longer than 50mm",
            "description": "Find edges exceeding length threshold",
            "category": "Edge Queries"
        },
        {
            "query": "vertices at z=0",
            "description": "Find vertices on the XY plane",
            "category": "Vertex Queries"
        },
        {
            "query": "show all vertices",
            "description": "Display all vertex points",
            "category": "Vertex Queries"
        },
        {
            "query": "find semicircular edges",
            "description": "Find edges that are semicircles (180-degree arcs)",
            "category": "Arc Queries"
        },
        {
            "query": "find quarter circle edges",
            "description": "Find edges that are quarter circles (90-degree arcs)",
            "category": "Arc Queries"
        },
        {
            "query": "arcs with radius 5mm",
            "description": "Find arcs with specific radius",
            "category": "Arc Queries"
        },
        {
            "query": "arcs with angle between 80 and 100 degrees",
            "description": "Find arcs within specific angle range",
            "category": "Arc Queries"
        },
        {
            "query": "fillet edges with radius 5mm",
            "description": "Find fillet arcs with specific radius",
            "category": "Arc Queries"
        }
    ]

    return {
        "examples": examples,
        "total_count": len(examples)
    }
