"""Laser ground truth benchmark verification schemas."""

from pydantic import BaseModel, Field


class LaserBenchmarkEntry(BaseModel):
    """Single benchmark trial entry comparing estimated vs laser ground truth."""

    target_id: int
    target_name: str
    laser_distance_m: float = Field(description="Ground truth measured with Bosch GLM (meters)")
    estimated_distance_m: float = Field(description="System predicted Z distance (meters)")


class BenchmarkResult(BaseModel):
    """Evaluation metrics for laser benchmark."""

    target_id: int
    laser_distance_m: float
    estimated_distance_m: float
    abs_error_m: float
    abs_rel_pct: float
    is_passed: bool = Field(description="True if AbsRel <= 5.0%")
