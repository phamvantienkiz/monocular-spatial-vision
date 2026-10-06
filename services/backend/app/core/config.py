"""Pydantic Settings for Backend Service.

Reads environment variables from .env and system configs.
"""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings schema."""

    env: str = Field(default="development", alias="ENV")
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Ingest TCP Server
    ingest_port: int = Field(default=9876, alias="INGEST_PORT")
    ring_buffer_size: int = Field(default=5, alias="RING_BUFFER_SIZE")

    # AI Model & TensorRT Engine
    model_engine_path: str = Field(default="weights/yolov8n-seg.engine", alias="MODEL_ENGINE_PATH")
    model_onnx_path: str = Field(default="weights/yolov8n-seg.onnx", alias="MODEL_ONNX_PATH")
    confidence_threshold: float = Field(default=0.50, alias="CONFIDENCE_THRESHOLD")

    # Camera Calibration File
    calib_config_path: str = Field(default="configs/calib_pcam5c.yaml", alias="CALIB_CONFIG_PATH")
    enable_imu_tilt_compensation: bool = Field(default=True, alias="ENABLE_IMU_TILT_COMPENSATION")

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
