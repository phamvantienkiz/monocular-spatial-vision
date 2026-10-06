"""Desktop OpenCV Live Viewer for Developer Laptop.

Reads the MJPEG live stream from Jetson AGX Xavier and renders in native desktop window.

Usage:
    python tools/laptop/live_hud_viewer.py --stream-url http://192.168.1.20:8000/api/v1/stream/live
"""

import argparse
import cv2


def run_viewer(url: str):
    print(f"[*] Opening live stream from {url}...")
    cap = cv2.VideoCapture(url)

    if not cap.isOpened():
        print(f"[!] Error: Could not connect to stream at {url}")
        return

    print("[+] Stream connected! Press 'q' to quit.")
    while True:
        ret, frame = cap.read()
        if not ret:
            print("[!] Stream disconnected or waiting for next frame...")
            break

        cv2.imshow("Jetson AGX Live Stream (Laptop Desktop Viewer)", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Live Desktop Stream Viewer")
    parser.add_argument("--stream-url", default="http://127.0.0.1:8000/api/v1/stream/live", help="MJPEG stream URL")
    args = parser.parse_args()
    run_viewer(args.stream_url)
