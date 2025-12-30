"""
Analysis API routes using C++ engine.

This is the new primary endpoint that uses the Analysis Situs C++ engine
for feature recognition.
"""

import logging
import uuid
from pathlib import Path
from fastapi import APIRouter, HTTPException, File, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Dict, Optional

from app.core.cpp_engine import get_engine, CppEngineError
from app.storage.model_store import ModelStore

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/analyze", tags=["analyze"])

# Data directory for storing models and results
DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)


class AnalyzeRequest(BaseModel):
    """Request to analyze a model with C++ engine"""
    model_id: str
    modules: str = "all"
    mesh_quality: float = 0.35


class AnalyzeResponse(BaseModel):
    """Response from analysis"""
    model_id: str
    success: bool
    features: List[Dict]
    metadata: Dict
    artifacts: Dict[str, str]  # URLs to download artifacts
    error: Optional[str] = None


class ModuleInfo(BaseModel):
    """Information about a recognizer module"""
    name: str
    type: str
    description: str


class ModuleListResponse(BaseModel):
    """List of available modules"""
    modules: List[ModuleInfo]
    total_count: int


@router.post("/upload", summary="Upload STEP file")
async def upload_step_file(file: UploadFile = File(...)):
    """
    Upload a STEP file for analysis.

    Returns:
        Dict with model_id for subsequent analysis
    """
    # Validate file extension
    if not file.filename.lower().endswith(('.step', '.stp')):
        raise HTTPException(
            status_code=400,
            detail="Only STEP files (.step, .stp) are supported"
        )

    # Generate model ID
    model_id = str(uuid.uuid4())
    model_dir = DATA_DIR / model_id
    model_dir.mkdir(parents=True, exist_ok=True)

    # Save uploaded file
    input_file = model_dir / "input.step"
    try:
        content = await file.read()
        input_file.write_bytes(content)
        logger.info(f"Uploaded {len(content)} bytes to {input_file}")
    except Exception as e:
        logger.error(f"Failed to save uploaded file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

    return {
        "model_id": model_id,
        "filename": file.filename,
        "size": len(content)
    }


@router.post("/process", response_model=AnalyzeResponse, summary="Analyze STEP file with C++ engine")
async def analyze_model(request: AnalyzeRequest):
    """
    Run feature recognition using the C++ Analysis Situs engine.

    This endpoint:
    1. Runs the C++ palmetto_engine binary
    2. Generates mesh.glb, tri_face_map.bin, features.json, etc.
    3. Returns feature recognition results

    Args:
        request: AnalyzeRequest with model_id and parameters

    Returns:
        AnalyzeResponse with features and artifact URLs
    """
    logger.info(f"Analysis request for model {request.model_id}")

    # Get model directory
    model_dir = DATA_DIR / request.model_id
    input_file = model_dir / "input.step"

    if not input_file.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Model {request.model_id} not found. Upload a file first."
        )

    # Create output directory
    output_dir = model_dir / "output"
    output_dir.mkdir(exist_ok=True)

    # Get C++ engine
    try:
        engine = get_engine()
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=503,
            detail=f"C++ engine not available: {str(e)}"
        )

    # Run analysis
    try:
        result = engine.process_step_file(
            input_file=input_file,
            output_dir=output_dir,
            modules=request.modules,
            mesh_quality=request.mesh_quality,
            timeout=300
        )

        # Build artifact URLs
        artifacts = {
            "mesh": f"/api/analyze/{request.model_id}/artifacts/mesh.glb",
            "tri_face_map": f"/api/analyze/{request.model_id}/artifacts/tri_face_map.bin",
            "features": f"/api/analyze/{request.model_id}/artifacts/features.json",
            "aag": f"/api/analyze/{request.model_id}/artifacts/aag.json",
            "metadata": f"/api/analyze/{request.model_id}/artifacts/meta.json",
            "topology": f"/api/analyze/{request.model_id}/artifacts/topology.json",
        }

        return AnalyzeResponse(
            model_id=request.model_id,
            success=result.success,
            features=result.features,
            metadata=result.metadata,
            artifacts=artifacts,
            error=result.error
        )

    except CppEngineError as e:
        logger.error(f"C++ engine error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    except Exception as e:
        logger.error(f"Unexpected error during analysis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.get("/{model_id}/artifacts/{filename}", summary="Download artifact")
async def get_artifact(model_id: str, filename: str):
    """
    Download an artifact generated by the C++ engine.

    Supported files:
    - mesh.glb - 3D mesh
    - tri_face_map.bin - Triangle to face mapping
    - features.json - Recognized features
    - aag.json - Attributed Adjacency Graph
    - meta.json - Processing metadata
    - topology.json - Topology geometry (vertices and edges)

    Args:
        model_id: Model identifier
        filename: Artifact filename

    Returns:
        File download
    """
    # Validate filename (security: prevent path traversal)
    allowed_files = {"mesh.glb", "tri_face_map.bin", "features.json", "aag.json", "meta.json", "topology.json"}
    if filename not in allowed_files:
        raise HTTPException(status_code=400, detail=f"Invalid artifact: {filename}")

    # Get file path
    file_path = DATA_DIR / model_id / "output" / filename

    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Artifact {filename} not found for model {model_id}"
        )

    # Determine media type
    media_types = {
        "mesh.glb": "model/gltf-binary",
        "tri_face_map.bin": "application/octet-stream",
        "features.json": "application/json",
        "aag.json": "application/json",
        "meta.json": "application/json",
        "topology.json": "application/json",
    }

    return FileResponse(
        path=file_path,
        media_type=media_types.get(filename, "application/octet-stream"),
        filename=filename
    )


@router.get("/modules", response_model=ModuleListResponse, summary="List available recognition modules")
async def list_modules():
    """
    List all available feature recognition modules from the C++ engine.

    Returns:
        ModuleListResponse with module information
    """
    try:
        engine = get_engine()
        modules = engine.list_modules()

        module_infos = [
            ModuleInfo(
                name=m.get("name", ""),
                type=m.get("type", ""),
                description=m.get("description", "")
            )
            for m in modules
        ]

        return ModuleListResponse(
            modules=module_infos,
            total_count=len(module_infos)
        )

    except Exception as e:
        logger.error(f"Failed to list modules: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list modules: {str(e)}")


@router.get("/health", summary="Check C++ engine health")
async def check_engine_health():
    """
    Check if the C++ engine is available and working.

    Returns:
        Health status
    """
    try:
        engine = get_engine()
        available = engine.check_available()

        return {
            "status": "healthy" if available else "unhealthy",
            "engine_path": engine.engine_path,
            "available": available
        }

    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "available": False
        }
