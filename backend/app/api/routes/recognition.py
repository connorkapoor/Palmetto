"""
Feature recognition API routes.
"""

import logging
import time
from fastapi import APIRouter, HTTPException

from app.api.schemas.recognition import (
    RecognitionRequest,
    RecognitionResponse,
    FeatureResult,
    RecognizerListResponse,
    RecognizerInfo
)
from app.storage.model_store import ModelStore
from app.recognizers.registry import RecognizerRegistry

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/recognition", tags=["recognition"])


@router.post("/recognize", response_model=RecognitionResponse)
async def recognize_features(request: RecognitionRequest):
    """
    Run a specific recognizer on a model.

    Args:
        request: RecognitionRequest with model_id, recognizer name, and parameters

    Returns:
        RecognitionResponse with recognized features
    """
    logger.info(f"Recognition request: {request.recognizer} on model {request.model_id}")

    # Get model from store
    graph = ModelStore.get_graph(request.model_id)
    if not graph:
        raise HTTPException(status_code=404, detail="Model not found")

    # Get recognizer
    recognizer_class = RecognizerRegistry.get(request.recognizer)
    if not recognizer_class:
        raise HTTPException(
            status_code=404,
            detail=f"Recognizer '{request.recognizer}' not found. "
                   f"Available: {RecognizerRegistry.list_all()}"
        )

    # Create recognizer instance
    recognizer = recognizer_class(graph)

    # Run recognition
    start_time = time.time()
    try:
        features = recognizer.recognize(**request.parameters)
    except Exception as e:
        logger.error(f"Recognition failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Recognition failed: {str(e)}")

    execution_time = time.time() - start_time

    # Convert to response format
    feature_results = [
        FeatureResult(
            feature_id=f.feature_id,
            feature_type=f.feature_type.value,
            confidence=f.confidence,
            face_ids=f.face_ids,
            properties=f.properties,
            bounding_geometry=f.bounding_geometry
        )
        for f in features
    ]

    logger.info(f"Recognition complete: {len(features)} features found in {execution_time:.2f}s")

    return RecognitionResponse(
        model_id=request.model_id,
        recognizer=request.recognizer,
        features=feature_results,
        execution_time=execution_time,
        feature_count=len(features)
    )


@router.get("/recognizers", response_model=RecognizerListResponse)
async def list_recognizers():
    """
    List all available recognizers.

    Returns:
        RecognizerListResponse with recognizer information
    """
    all_info = RecognizerRegistry.get_all_info()

    recognizer_infos = [
        RecognizerInfo(
            name=info['name'],
            description=info['description'],
            feature_types=info['feature_types']
        )
        for info in all_info
    ]

    return RecognizerListResponse(
        recognizers=recognizer_infos,
        total_count=len(recognizer_infos)
    )


@router.get("/recognizers/{name}")
async def get_recognizer_info(name: str):
    """
    Get detailed information about a specific recognizer.

    Args:
        name: Recognizer name

    Returns:
        Recognizer information
    """
    info = RecognizerRegistry.get_recognizer_info(name)

    if not info:
        raise HTTPException(status_code=404, detail=f"Recognizer '{name}' not found")

    return info
