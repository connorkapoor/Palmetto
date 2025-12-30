"""
API schemas for feature recognition endpoints.
"""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any


class RecognitionRequest(BaseModel):
    """Request to recognize features in a model."""
    model_id: str = Field(..., description="Model identifier")
    recognizer: str = Field(..., description="Name of recognizer to use")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Recognizer-specific parameters")


class FeatureResult(BaseModel):
    """Result of a recognized feature."""
    feature_id: str
    feature_type: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    face_ids: List[str]
    properties: Dict[str, Any]
    bounding_geometry: Optional[Any] = None


class RecognitionResponse(BaseModel):
    """Response from feature recognition."""
    model_id: str
    recognizer: str
    features: List[FeatureResult]
    execution_time: float = Field(..., description="Execution time in seconds")
    feature_count: int


class RecognizerInfo(BaseModel):
    """Information about a recognizer."""
    name: str
    description: str
    feature_types: List[str]
    parameters: Optional[Dict[str, Any]] = None


class RecognizerListResponse(BaseModel):
    """Response containing list of available recognizers."""
    recognizers: List[RecognizerInfo]
    total_count: int


class NLRequest(BaseModel):
    """Natural language recognition request."""
    model_id: str = Field(..., description="Model identifier")
    command: str = Field(..., description="Natural language command")


class NLResponse(BaseModel):
    """Response from natural language processing."""
    model_id: str
    command: str
    recognized_intent: Dict[str, Any]
    recognizer: str
    features: List[FeatureResult]
    execution_time: float
