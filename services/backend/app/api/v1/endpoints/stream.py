"""Live MJPEG video streaming endpoint with 2D/3D visual overlay.

Yields multipart/x-mixed-replace frame chunks from the Ingest Service for
low-latency browser consumption on the Developer Laptop Web HUD.
"""

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import time

from app.services.ingest_service import get_ingest_service

router = APIRouter()


def generate_mjpeg_stream():
    """Generator yielding multipart MJPEG frames from the Ingest Service."""
    ingest = get_ingest_service()
    while True:
        frame_tuple = ingest.get_latest_frame()
        if frame_tuple is not None:
            _, _, jpeg_bytes = frame_tuple
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + jpeg_bytes + b"\r\n"
            )
        time.sleep(0.033)  # ~30 FPS


@router.get("/stream/live")
def get_live_stream():
    """Returns real-time video stream over HTTP MJPEG."""
    return StreamingResponse(
        generate_mjpeg_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )
