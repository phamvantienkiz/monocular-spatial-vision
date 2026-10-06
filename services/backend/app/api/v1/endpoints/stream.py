"""Live MJPEG video streaming endpoint with 2D/3D visual overlay.

TODO for Students:
- Consume latest processed frame from perception pipeline.
- Draw 3D wireframe bounding boxes and red contact point (#EF4444).
- Encode to JPEG byte stream.
- Yield multipart/x-mixed-replace frame chunks for browser consumption.
"""

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import time

router = APIRouter()


def generate_mjpeg_stream():
    """Generator yielding multipart MJPEG frames."""
    # TODO: Students hook up real perception frame stream here
    while True:
        time.sleep(0.033)  # ~30 FPS placeholder
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + b"" + b"\r\n"
        )


@router.get("/stream/live")
def get_live_stream():
    """Returns real-time annotated video stream over HTTP MJPEG."""
    return StreamingResponse(
        generate_mjpeg_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )
