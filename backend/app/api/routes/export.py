"""
Model export API routes.
"""

import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.api.schemas.export import ExportRequest, ExportResponse
from app.storage.model_store import ModelStore
from app.core.meshing.tessellator import Tessellator
from app.core.meshing.gltf_exporter import GLTFExporter
from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/export", tags=["export"])

settings = get_settings()


@router.post("/gltf", response_class=Response)
async def export_to_gltf(request: ExportRequest):
    """
    Export model to glTF format.

    Args:
        request: ExportRequest with model_id and export options

    Returns:
        glTF binary file (GLB)
    """
    logger.info(f"Export request for model {request.model_id}")

    # Get model from store
    model = ModelStore.get(request.model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    # Get tessellation parameters
    linear_def = request.linear_deflection or settings.linear_deflection
    angular_def = request.angular_deflection or settings.angular_deflection

    # Tessellate
    logger.info("Tessellating...")
    tessellator = Tessellator(model.shape, linear_def, angular_def)

    try:
        vertices, triangles, face_map = tessellator.tessellate()
    except Exception as e:
        logger.error(f"Tessellation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Tessellation failed: {str(e)}")

    # Build feature highlights if requested
    feature_highlights = None
    if request.include_features and request.feature_ids:
        # For now, just map feature IDs to their face IDs
        # In a real implementation, we'd retrieve stored features
        feature_highlights = {fid: [] for fid in request.feature_ids}

    # Export to glTF
    logger.info("Exporting to glTF...")
    exporter = GLTFExporter(vertices, triangles, face_map)

    try:
        gltf_bytes = exporter.export_to_bytes(feature_highlights)
    except Exception as e:
        logger.error(f"glTF export failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"glTF export failed: {str(e)}")

    logger.info(f"Export complete: {len(gltf_bytes)} bytes")

    # Return glTF binary
    return Response(
        content=gltf_bytes,
        media_type="model/gltf-binary",
        headers={
            "Content-Disposition": f'attachment; filename="{model.filename}.glb"'
        }
    )


@router.post("/gltf/info", response_model=ExportResponse)
async def get_export_info(request: ExportRequest):
    """
    Get information about what would be exported (without actually exporting).

    Args:
        request: ExportRequest

    Returns:
        ExportResponse with export statistics
    """
    # Get model from store
    model = ModelStore.get(request.model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    # Get tessellation parameters
    linear_def = request.linear_deflection or settings.linear_deflection
    angular_def = request.angular_deflection or settings.angular_deflection

    # Tessellate
    tessellator = Tessellator(model.shape, linear_def, angular_def)
    vertices, triangles, face_map = tessellator.tessellate()

    # Get statistics
    mesh_stats = tessellator.get_mesh_statistics(vertices, triangles, face_map)

    # Estimate file size (rough approximation)
    estimated_size = (
        len(vertices) * 12 +  # 3 floats per vertex
        len(triangles) * 12 +  # 3 uints per triangle
        1024  # glTF overhead
    )

    return ExportResponse(
        model_id=request.model_id,
        filename=f"{model.filename}.glb",
        format="glb",
        file_size=estimated_size,
        mesh_stats=mesh_stats
    )
