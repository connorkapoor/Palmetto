"""
Natural language interface API routes.
"""

import logging
import time
from fastapi import APIRouter, HTTPException

from app.api.schemas.recognition import NLRequest, NLResponse, FeatureResult
from app.storage.model_store import ModelStore
from app.nl_processing.intent_parser import IntentParser
from app.recognizers.registry import RecognizerRegistry

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/nl", tags=["natural-language"])


@router.post("/parse", response_model=NLResponse)
async def parse_and_execute(request: NLRequest):
    """
    Parse natural language command and execute feature recognition.

    This is the main natural language interface endpoint that:
    1. Parses the command using Claude API
    2. Maps to appropriate recognizer
    3. Executes recognition
    4. Returns results

    Args:
        request: NLRequest with model_id and natural language command

    Returns:
        NLResponse with parsed intent and recognized features

    Example:
        POST /api/nl/parse
        {
            "model_id": "abc123",
            "command": "find all holes larger than 10mm"
        }

        Response:
        {
            "model_id": "abc123",
            "command": "find all holes larger than 10mm",
            "recognized_intent": {
                "recognizer": "hole_detector",
                "parameters": {"min_diameter": 10.0},
                "confidence": 0.95
            },
            "recognizer": "hole_detector",
            "features": [...],
            "execution_time": 1.23
        }
    """
    logger.info(f"NL request: '{request.command}' for model {request.model_id}")

    start_time = time.time()

    # Get model from store
    graph = ModelStore.get_graph(request.model_id)
    if not graph:
        raise HTTPException(status_code=404, detail="Model not found")

    # Parse intent
    parser = IntentParser()

    try:
        intent = parser.parse(request.command)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Intent parsing failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to parse command: {str(e)}")

    # Get recognizer
    recognizer_class = RecognizerRegistry.get(intent["recognizer"])
    if not recognizer_class:
        raise HTTPException(
            status_code=404,
            detail=f"Recognizer '{intent['recognizer']}' not found"
        )

    # Create recognizer instance
    recognizer = recognizer_class(graph)

    # Run recognition
    try:
        features = recognizer.recognize(**intent["parameters"])
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

    logger.info(f"NL recognition complete: {len(features)} features found in {execution_time:.2f}s")

    return NLResponse(
        model_id=request.model_id,
        command=request.command,
        recognized_intent=intent,
        recognizer=intent["recognizer"],
        features=feature_results,
        execution_time=execution_time
    )
