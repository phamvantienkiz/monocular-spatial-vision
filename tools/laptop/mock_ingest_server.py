"""Mock Ingest Server for Developer Laptop.

Listens on TCP port 9876, receives packets from Raspberry Pi 3,
unpacks 40-byte binary header, displays frame in OpenCV window, and prints telemetry stats.

Usage:
    python tools/laptop/mock_ingest_server.py --port 9876
"""

import argparse
import collections
import socket
import struct
import threading
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
        client_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        client_sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 1024)

        frame_buffer = collections.deque(maxlen=2)
        stop_event = threading.Event()
        start_time = time.time()
        frame_counter = [0]

        def _receiver_worker():
            try:
                while not stop_event.is_set():
                    # Read 40-byte header
                    header_data = bytearray()
                    while len(header_data) < HEADER_SIZE and not stop_event.is_set():
                        packet = client_sock.recv(HEADER_SIZE - len(header_data))
                        if not packet:
                            return
                        header_data.extend(packet)

                    if len(header_data) < HEADER_SIZE:
                        return

                    magic, ver, f_id, ts, pitch, roll, p_len, w, h, _ = struct.unpack(HEADER_FORMAT, header_data)
                    if magic != MAGIC_NUMBER:
                        print(f"[!] Warning: Invalid magic number 0x{magic:04X}")
                        continue

                    # Read image payload
                    payload = bytearray()
                    while len(payload) < p_len and not stop_event.is_set():
                        packet = client_sock.recv(p_len - len(payload))
                        if not packet:
                            return
                        payload.extend(packet)

                    if len(payload) < p_len:
                        return

                    frame_counter[0] += 1
                    elapsed = max(time.time() - start_time, 1e-6)
                    fps = frame_counter[0] / elapsed
                    frame_buffer.append((f_id, ts, pitch, roll, payload, fps))
            except (ConnectionResetError, BrokenPipeError, OSError):
                pass
            finally:
                stop_event.set()

        recv_thread = threading.Thread(target=_receiver_worker, daemon=True)
        recv_thread.start()

        try:
            while not stop_event.is_set():
                if frame_buffer:
                    f_id, ts, pitch, roll, payload, fps = frame_buffer.pop()
                    img_arr = np.frombuffer(payload, dtype=np.uint8)
                    frame = cv2.imdecode(img_arr, cv2.IMREAD_COLOR)

                    if frame is not None:
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

                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    stop_event.set()
                    break
        except KeyboardInterrupt:
            stop_event.set()
        except Exception as e:
            print(f"[!] Display error: {e}")
            stop_event.set()
        finally:
            stop_event.set()
            recv_thread.join(timeout=1.0)
            client_sock.close()
            cv2.destroyAllWindows()
            print("[-] Client disconnected / session ended. Waiting for next connection...\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mock Ingest Server on Developer Laptop")
    parser.add_argument("--port", type=int, default=9876, help="TCP port to listen on")
    args = parser.parse_args()
    run_mock_server(args.port)
