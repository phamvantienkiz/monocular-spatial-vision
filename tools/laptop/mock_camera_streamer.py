"""Mock Camera Streamer for Developer Laptop.

Pumps a pre-recorded video or image directory from Laptop to Jetson AGX Xavier
over TCP socket (port 9876), packing frames with valid 36-byte binary headers.

Usage:
    python tools/laptop/mock_camera_streamer.py --video sample.mp4 --target-host 192.168.1.20 --port 9876
"""

import argparse
import socket
import struct
import time
import cv2

HEADER_FORMAT = ">HHIQffIIII"
MAGIC_NUMBER = 0x5043
PROTOCOL_VERSION = 1


def stream_video(video_path: str, host: str, port: int, fps: int = 30):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"[!] Error: Unable to open video {video_path}")
        return

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    print(f"[*] Connecting to Jetson at {host}:{port}...")
    sock.connect((host, port))
    print("[+] Connected! Streaming synthetic frames...")

    frame_id = 0
    frame_interval = 1.0 / fps

    try:
        while True:
            start_t = time.time()
            ret, frame = cap.read()
            if not ret:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue

            # Resize to standard 1280x720 if needed
            if frame.shape[1] != 1280 or frame.shape[0] != 720:
                frame = cv2.resize(frame, (1280, 720))

            _, enc = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            image_bytes = enc.tobytes()

            timestamp_ns = time.time_ns()
            pitch_deg = 12.5
            roll_deg = 0.0

            header = struct.pack(
                HEADER_FORMAT,
                MAGIC_NUMBER,
                PROTOCOL_VERSION,
                frame_id,
                timestamp_ns,
                pitch_deg,
                roll_deg,
                len(image_bytes),
                1280,
                720,
                0,
            )

            sock.sendall(header + image_bytes)
            frame_id += 1

            elapsed = time.time() - start_t
            if elapsed < frame_interval:
                time.sleep(frame_interval - elapsed)

    except KeyboardInterrupt:
        print("\n[*] Streaming stopped by user.")
    finally:
        cap.release()
        sock.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mock Camera Streamer")
    parser.add_argument("--video", required=True, help="Path to test MP4 video")
    parser.add_argument("--target-host", default="127.0.0.1", help="Target ingest host IP")
    parser.add_argument("--port", type=int, default=9876, help="Target ingest TCP port")
    parser.add_argument("--fps", type=int, default=30, help="Framerate")
    args = parser.parse_args()
    stream_video(args.video, args.target_host, args.port, args.fps)
