"""Mock Ingest Server for Developer Laptop.

Listens on TCP port 9876, receives packets from Raspberry Pi 3,
unpacks 36-byte binary header, displays frame in OpenCV window, and prints telemetry stats.

Usage:
    python tools/laptop/mock_ingest_server.py --port 9876
"""

import argparse
import socket
import struct
import time
import cv2
import numpy as np

HEADER_FORMAT = ">HHIQffIIII"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
MAGIC_NUMBER = 0x5043


def run_mock_server(port: int = 9876):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", port))
    server.listen(1)
    print(f"[*] Mock Ingest Server listening on 0.0.0.0:{port}...")

    while True:
        client_sock, client_addr = server.accept()
        print(f"[+] Client connected from {client_addr}")
        frame_count = 0
        start_time = time.time()

        try:
            while True:
                # Read 36-byte header
                header_data = bytearray()
                while len(header_data) < HEADER_SIZE:
                    packet = client_sock.recv(HEADER_SIZE - len(header_data))
                    if not packet:
                        break
                    header_data.extend(packet)

                if len(header_data) < HEADER_SIZE:
                    break

                magic, ver, f_id, ts, pitch, roll, p_len, w, h, _ = struct.unpack(HEADER_FORMAT, header_data)
                if magic != MAGIC_NUMBER:
                    print(f"[!] Warning: Invalid magic number 0x{magic:04X}")
                    continue

                # Read image payload
                payload = bytearray()
                while len(payload) < p_len:
                    packet = client_sock.recv(p_len - len(payload))
                    if not packet:
                        break
                    payload.extend(packet)

                if len(payload) < p_len:
                    break

                frame_count += 1
                fps = frame_count / (time.time() - start_time)

                # Decode JPEG image
                img_arr = np.frombuffer(payload, dtype=np.uint8)
                frame = cv2.imdecode(img_arr, cv2.IMREAD_COLOR)

                if frame is not None:
                    # Draw telemetry text on frame
                    cv2.putText(
                        frame,
                        f"Frame: #{f_id} | FPS: {fps:.1f} | Pitch: {pitch:.2f} deg | Roll: {roll:.2f} deg",
                        (20, 30),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (0, 255, 0),
                        2,
                    )
                    cv2.imshow("Pi 3 Stream (Mock Ingest on Laptop)", frame)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break

        except ConnectionResetError:
            print("[-] Client disconnected.")
        finally:
            client_sock.close()
            cv2.destroyAllWindows()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mock Ingest Server on Developer Laptop")
    parser.add_argument("--port", type=int, default=9876, help="TCP port to listen on")
    args = parser.parse_args()
    run_mock_server(args.port)
