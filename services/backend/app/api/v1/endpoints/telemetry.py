"""Telemetry REST and WebSocket endpoints."""

import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.schemas.telemetry import TelemetryData, FrameStats

router = APIRouter()


@router.get("/telemetry", response_model=TelemetryData)
def get_latest_telemetry():
    """Returns the most recent single telemetry snapshot."""
    # TODO: Students connect this to ingest/geometry state
    return TelemetryData(
        frame_id=100,
        timestamp_ns=1775460000000000,
        pitch_deg=12.48,
        roll_deg=-0.12,
        camera_height_m=0.285,
    )


@router.websocket("/ws/telemetry")
async def websocket_telemetry_stream(websocket: WebSocket):
    """Streams real-time telemetry and object detection coordinates over WebSocket."""
    await websocket.accept()
    try:
        while True:
            # TODO: Students push actual telemetry JSON payload at 30Hz
            payload = {
                "frame_id": 1,
                "pitch_deg": 12.48,
                "roll_deg": -0.12,
                "camera_height_m": 0.285,
                "fps": 30.0,
                "objects": [
                    {
                        "id": 1,
                        "class_name": "person",
                        "pos_xyz": [0.15, 0.02, 1.84],
                        "size_lwh": [0.45, 0.50, 1.65],
                        "distance_z": 1.84,
                    }
                ],
            }
            await websocket.send_json(payload)
            await asyncio.sleep(0.033)
    except WebSocketDisconnect:
        pass
