"""Telemetry REST and WebSocket endpoints."""

import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.schemas.telemetry import TelemetryData
from app.services.ingest_service import get_ingest_service
from app.core.config import settings

router = APIRouter()


@router.get("/telemetry", response_model=TelemetryData)
def get_latest_telemetry():
    """Returns the most recent single telemetry snapshot from IngestService."""
    ingest = get_ingest_service()
    telem = ingest.get_latest_telemetry()
    if telem is not None:
        return TelemetryData(
            frame_id=telem.get("frame_id", 0),
            timestamp_ns=telem.get("timestamp_ns", 0),
            pitch_deg=round(telem.get("pitch_deg", 0.0), 2),
            roll_deg=round(telem.get("roll_deg", 0.0), 2),
            camera_height_m=getattr(settings, "camera_height_m", 0.285),
        )
    return TelemetryData(
        frame_id=0,
        timestamp_ns=0,
        pitch_deg=0.0,
        roll_deg=0.0,
        camera_height_m=getattr(settings, "camera_height_m", 0.285),
    )


@router.websocket("/ws/telemetry")
async def websocket_telemetry_stream(websocket: WebSocket):
    """Streams real-time telemetry and object detection coordinates over WebSocket."""
    await websocket.accept()
    ingest = get_ingest_service()
    try:
        while True:
            telem = ingest.get_latest_telemetry()
            fps = ingest.get_fps()
            if telem is not None:
                payload = {
                    "frame_id": telem.get("frame_id", 0),
                    "pitch_deg": round(telem.get("pitch_deg", 0.0), 2),
                    "roll_deg": round(telem.get("roll_deg", 0.0), 2),
                    "camera_height_m": getattr(settings, "camera_height_m", 0.285),
                    "fps": round(fps, 1),
                    "objects": [],
                }
            else:
                payload = {
                    "frame_id": 0,
                    "pitch_deg": 0.0,
                    "roll_deg": 0.0,
                    "camera_height_m": getattr(settings, "camera_height_m", 0.285),
                    "fps": 0.0,
                    "objects": [],
                }
            await websocket.send_json(payload)
            await asyncio.sleep(0.033)
    except WebSocketDisconnect:
        pass
