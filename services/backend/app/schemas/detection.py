"""Object detection and 3D spatial estimation schemas."""

from typing import List, Tuple
from pydantic import BaseModel, Field


class Detection2D(BaseModel):
    """2D object detection bounding box and mask point."""

    class_id: int
    class_name: str
    confidence: float
    bbox_xyxy: Tuple[float, float, float, float]
    contact_point_uv: Tuple[int, int] = Field(description="Extracted bottom contact point (u, v)")


class BoundingBox3D(BaseModel):
    """3D bounding box in camera optical coordinates."""

    position_xyz: Tuple[float, float, float] = Field(description="Center coordinates (X, Y, Z) in meters")
    size_lwh: Tuple[float, float, float] = Field(description="Bounding box dimensions (Length, Width, Height) in meters")


class DetectionResult(BaseModel):
    """Combined 2D and 3D detection output."""

    id: int
    det2d: Detection2D
    bbox3d: BoundingBox3D
    distance_z_m: float
