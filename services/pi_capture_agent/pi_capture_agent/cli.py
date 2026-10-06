"""Command-line interface entrypoint for Raspberry Pi 3 capture agent.

TODO for Students:
- Parse command line arguments: --mode, --config, --output, --host, --port.
- Dispatch to corresponding workflows:
  * snapshot: captures a single test frame and writes to disk.
  * preview: starts a lightweight HTTP server serving a single JPEG snapshot.
  * test-imu: prints raw and filtered IMU angles to terminal.
  * stream: runs the continuous streaming loop to the remote ingest server.
"""

import argparse
import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("pi_capture_agent")


def main() -> None:
    parser = argparse.ArgumentParser(description="Raspberry Pi 3 Pcam 5C & IMU Capture Agent")
    parser.add_argument(
        "--mode",
        choices=["snapshot", "preview", "test-imu", "stream"],
        default="stream",
        help="Operating mode (default: stream)",
    )
    parser.add_argument("--config", default="configs/capture_pi.yaml", help="Path to config YAML")
    parser.add_argument("--output", default="data/test_frame.jpg", help="Path to save test image")
    parser.add_argument("--host", default=None, help="Target ingest host IP (overrides config)")
    parser.add_argument("--port", type=int, default=None, help="Target ingest port (overrides config)")

    args = parser.parse_args()
    logger.info("Starting pi_capture_agent with mode: %s", args.mode)

    if args.mode == "snapshot":
        logger.info("TODO: Implement single frame snapshot to %s", args.output)
    elif args.mode == "preview":
        logger.info("TODO: Implement diagnostic HTTP preview server")
    elif args.mode == "test-imu":
        logger.info("TODO: Implement IMU readout loop")
    elif args.mode == "stream":
        logger.info("TODO: Implement continuous camera + IMU binary stream")
    else:
        logger.error("Unknown mode: %s", args.mode)
        sys.exit(1)


if __name__ == "__main__":
    main()
