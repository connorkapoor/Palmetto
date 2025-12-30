"""
API schemas for file upload endpoints.
"""

from pydantic import BaseModel, Field
from typing import Dict, Optional, Any


class UploadResponse(BaseModel):
    """Response after successful file upload."""
    model_id: str = Field(..., description="Unique identifier for uploaded model")
    filename: str = Field(..., description="Original filename")
    file_format: str = Field(..., description="File format (step, iges, brep)")
    topology_stats: Dict[str, int] = Field(..., description="Topology statistics (vertices, edges, faces)")
    message: str = Field(default="Model uploaded successfully")


class ModelInfo(BaseModel):
    """Information about a stored model."""
    model_id: str
    filename: str
    file_format: str
    uploaded_at: str
    last_accessed: str
    age_seconds: float
    topology_stats: Dict[str, int]
    metadata: Dict[str, Any]


class ModelListResponse(BaseModel):
    """Response containing list of models."""
    models: list[ModelInfo]
    total_count: int
