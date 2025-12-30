"""
File upload API routes.
"""

import os
import tempfile
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

from app.api.schemas.upload import UploadResponse, ModelListResponse, ModelInfo
from app.core.cad_loader import CADLoader, CADLoadError
from app.core.topology.builder import AAGBuilder
from app.storage.model_store import ModelStore
from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/upload", tags=["upload"])

settings = get_settings()


@router.post("/", response_model=UploadResponse)
async def upload_cad_file(file: UploadFile = File(...)):
    """
    Upload a CAD file (STEP, IGES, or BREP).

    The file will be:
    1. Validated for format
    2. Loaded as B-Rep
    3. Converted to AAG
    4. Stored in memory

    Returns:
        UploadResponse with model_id and topology statistics
    """
    logger.info(f"Received upload: {file.filename}")

    # Validate file format
    if not CADLoader.is_supported_format(file.filename):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format. Supported: {list(CADLoader.SUPPORTED_FORMATS.keys())}"
        )

    # Check file size
    file_content = await file.read()
    file_size = len(file_content)

    if file_size > settings.max_upload_size:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size: {settings.max_upload_size} bytes"
        )

    # Save to temporary file
    temp_file = None
    try:
        # Create temp file
        suffix = os.path.splitext(file.filename)[1]
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(file_content)
            temp_file = tmp.name

        logger.info(f"Saved to temp file: {temp_file}")

        # Load CAD file
        try:
            shape = CADLoader.load(temp_file)
        except CADLoadError as e:
            raise HTTPException(status_code=400, detail=f"Failed to load CAD file: {str(e)}")

        # Build AAG
        logger.info("Building AAG...")
        builder = AAGBuilder(shape)
        graph = builder.build()

        # Store in model store
        file_format = CADLoader.get_format_from_extension(file.filename)
        model_id = ModelStore.store(
            shape=shape,
            graph=graph,
            filename=file.filename,
            file_format=file_format,
            metadata={'original_size': file_size}
        )

        # Get statistics
        stats = graph.get_statistics()

        logger.info(f"Upload complete: {model_id}")

        return UploadResponse(
            model_id=model_id,
            filename=file.filename,
            file_format=file_format,
            topology_stats=stats
        )

    except Exception as e:
        logger.error(f"Upload failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

    finally:
        # Cleanup temp file
        if temp_file and os.path.exists(temp_file):
            try:
                os.unlink(temp_file)
            except Exception as e:
                logger.warning(f"Failed to delete temp file: {e}")


@router.get("/models", response_model=ModelListResponse)
async def list_models():
    """
    List all uploaded models.

    Returns:
        ModelListResponse with list of stored models
    """
    models = ModelStore.list_models()

    model_infos = [
        ModelInfo(**model) for model in models
    ]

    return ModelListResponse(
        models=model_infos,
        total_count=len(model_infos)
    )


@router.get("/models/{model_id}")
async def get_model_info(model_id: str):
    """
    Get information about a specific model.

    Args:
        model_id: Model identifier

    Returns:
        Model information
    """
    model = ModelStore.get(model_id)

    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    stats = model.graph.get_statistics()

    return {
        "model_id": model.model_id,
        "filename": model.filename,
        "file_format": model.file_format,
        "uploaded_at": model.uploaded_at.isoformat(),
        "topology_stats": stats,
        "metadata": model.metadata
    }


@router.delete("/models/{model_id}")
async def delete_model(model_id: str):
    """
    Delete a model from storage.

    Args:
        model_id: Model identifier

    Returns:
        Confirmation message
    """
    if not ModelStore.exists(model_id):
        raise HTTPException(status_code=404, detail="Model not found")

    ModelStore.delete(model_id)

    return {"message": f"Model {model_id} deleted successfully"}
