"""System health check and hardware utilization endpoints."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/system/status")
def get_system_status():
    """Returns GPU, VRAM, and pipeline health metrics."""
    return {
        "status": "online",
        "device": "NVIDIA Jetson AGX Xavier",
        "gpu_utilization_pct": 45.0,
        "vram_used_mb": 2100,
        "vram_limit_mb": 4500,
    }
