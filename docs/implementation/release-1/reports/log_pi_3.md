(.venv) r3b@r3b:~/workspaces/monocular-spatial-vision/services/pi_capture_agent $ python -m pi_capture_agent.cli --mode test-perf --frames 100
2026-10-19 15:29:14,684 [INFO] Loaded configuration from: /home/r3b/workspaces/monocular-spatial-vision/configs/capture_pi.yaml
2026-10-19 15:29:14,686 [INFO] Selected mode: test-perf
====================================================================
PI CAPTURE AGENT — PERFORMANCE BENCHMARK (100 FRAMES)
====================================================================
2026-10-19 15:29:15,470 [INFO] Negotiated media-ctl pipeline: ov5640 10-003c:0 -> 1280x720 @ 30 FPS UYVY
2026-10-19 15:29:15,535 [INFO] Hardware vertical flip enabled successfully on /dev/v4l-subdev0
[ WARN:0@1.115] global cap_v4l.cpp:1844 getProperty VIDEOIO(V4L2:/dev/video0): Unable to get camera FPS
2026-10-19 15:29:16,368 [INFO] Camera /dev/video0 opened: 1280x720 @ -1.0 FPS (Requested 1280x720 @ 30 FPS, fmt=UYVY)
Camera Device: /dev/video0 (1280x720, fmt=UYVY)
Hardware Flip: ACTIVE (Sensor OV5640 hardware)
JPEG Backend: PyTurboJPEG (ARM NEON SIMD)
JPEG Quality: 70
Running warmup frames...
Benchmarking 100 frames...
2026-10-19 15:29:26,905 [INFO] Camera device released.

---

Avg Raw Grab Time: 41.29 ms
Avg Encode Time: 60.62 ms
Sequential Cycle Time: 101.91 ms ( 9.8 FPS)
Pipelined Throughput: 16.5 FPS (Target in Threaded Mode)
Avg JPEG Payload Size: 51.8 KB
====================================================================
RESULT: [NOTICE] Below 25 FPS target; verify hardware acceleration or downscale to 640x360.
====================================================================
