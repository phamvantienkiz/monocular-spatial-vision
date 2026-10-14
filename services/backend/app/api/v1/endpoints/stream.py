"""Live MJPEG video streaming endpoint with 2D/3D visual overlay.

Streams frames received by IngestService directly to Web HUD and client browsers.
"""

import time
import cv2
import numpy as np
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.services.ingest_service import get_ingest_service

router = APIRouter()


def _create_placeholder_frame(text: str = "Waiting for Camera Stream...") -> bytes:
    """Creates a simple placeholder JPEG when no camera is connected."""
    img = np.zeros((360, 640, 3), dtype=np.uint8)
    cv2.putText(
        img,
        text,
        (130, 185),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (156, 163, 175),
        2,
        cv2.LINE_AA,
    )
    success, enc = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 70])
    return enc.tobytes() if success else b""


_PLACEHOLDER_JPEG = _create_placeholder_frame("Waiting for Camera Stream...")


def generate_mjpeg_stream():
    """Generator yielding multipart MJPEG frames from the Ingest Service."""
    ingest = get_ingest_service()
    last_frame_id = -1

    while True:
        pkg = ingest.get_latest_package()
        if pkg is not None:
            header, _bgr, jpeg_bytes = pkg
            f_id = header.get("frame_id", 0)
            if f_id != last_frame_id:
                last_frame_id = f_id
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + jpeg_bytes + b"\r\n"
                )
                time.sleep(0.005)
                continue
            else:
                # Same frame, sleep briefly (~15ms)
                time.sleep(0.015)
        else:
            # Yield placeholder frame while waiting for Pi connection
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + _PLACEHOLDER_JPEG + b"\r\n"
            )
            time.sleep(0.5)


@router.get("/stream/live")
def get_live_stream():
    """Returns real-time annotated video stream over HTTP MJPEG."""
    return StreamingResponse(
        generate_mjpeg_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )
