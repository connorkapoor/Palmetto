"""
API schemas for export endpoints.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class ExportRequest(BaseModel):
    """Request to export model to glTF."""
    model_id: str = Field(..., description="Model identifier")
    include_features: bool = Field(default=False, description="Include feature highlights")
    feature_ids: List[str] = Field(default_factory=list, description="Specific features to highlight")
    linear_deflection: Optional[float] = Field(default=None, description="Tessellation linear deflection")
    angular_deflection: Optional[float] = Field(default=None, description="Tessellation angular deflection")


class ExportResponse(BaseModel):
    """Response from glTF export."""
    model_id: str
    filename: str
    format: str = "glb"
    file_size: int = Field(..., description="File size in bytes")
    mesh_stats: Dict[str, Any]
    message: str = "Export successful"
