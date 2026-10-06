"""Telemetry and performance metrics schemas."""

from pydantic import BaseModel, Field


class TelemetryData(BaseModel):
    """Instantaneous attitude and camera geometry telemetry."""

    frame_id: int = Field(default=0, description="Sequential frame identifier")
    timestamp_ns: int = Field(default=0, description="Capture timestamp in nanoseconds")
    pitch_deg: float = Field(default=12.5, description="Current camera pitch angle (degrees)")
    roll_deg: float = Field(default=0.0, description="Current camera roll angle (degrees)")
    camera_height_m: float = Field(default=0.285, description="Measured camera optical center height (m)")


class FrameStats(BaseModel):
    """Pipeline runtime latency and throughput stats."""

    fps: float = Field(default=30.0, description="Ingest and inference framerate")
    ingest_latency_ms: float = Field(default=2.5, description="Network ingestion duration")
    inference_latency_ms: float = Field(default=15.0, description="TensorRT inference duration")
    ipm_latency_ms: float = Field(default=1.0, description="IPM ground solve duration")
    total_e2e_latency_ms: float = Field(default=35.0, description="End-to-end latency from Pi to Jetson output")
