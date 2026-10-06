"""Data transfer schemas (Pydantic models) for the backend."""

from app.schemas.telemetry import TelemetryData, FrameStats
from app.schemas.detection import Detection2D, BoundingBox3D, DetectionResult
from app.schemas.benchmark import LaserBenchmarkEntry, BenchmarkResult

__all__ = [
    "TelemetryData",
    "FrameStats",
    "Detection2D",
    "BoundingBox3D",
    "DetectionResult",
    "LaserBenchmarkEntry",
    "BenchmarkResult",
]
