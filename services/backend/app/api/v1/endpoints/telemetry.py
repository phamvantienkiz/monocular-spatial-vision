"""Telemetry REST and WebSocket endpoints."""

import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.schemas.telemetry import TelemetryData
from app.services.ingest_service import get_ingest_service

router = APIRouter()


@router.get("/telemetry", response_model=TelemetryData)
def get_latest_telemetry():
    """Returns the most recent single telemetry snapshot."""
    ingest = get_ingest_service()
    telem = ingest.get_latest_telemetry()
    return TelemetryData(
        frame_id=telem.get("frame_id", 0),
        timestamp_ns=telem.get("timestamp_ns", 0),
        pitch_deg=telem.get("pitch_deg", 12.5),
        roll_deg=telem.get("roll_deg", 0.0),
        camera_height_m=telem.get("camera_height_m", 0.285),
    )


@router.websocket("/ws/telemetry")
async def websocket_telemetry_stream(websocket: WebSocket):
    """Streams real-time telemetry and attitude coordinates over WebSocket at 30Hz."""
    await websocket.accept()
    ingest = get_ingest_service()
    try:
        while True:
            telem = ingest.get_latest_telemetry()
            payload = {
                "frame_id": telem.get("frame_id", 0),
                "timestamp_ns": telem.get("timestamp_ns", 0),
                "pitch_deg": telem.get("pitch_deg", 12.5),
                "roll_deg": telem.get("roll_deg", 0.0),
                "camera_height_m": telem.get("camera_height_m", 0.285),
                "fps": telem.get("fps", 0.0),
                "is_streaming": telem.get("is_streaming", False),
                "objects": [],
            }
            await websocket.send_json(payload)
            await asyncio.sleep(0.033)
    except WebSocketDisconnect:
        pass
