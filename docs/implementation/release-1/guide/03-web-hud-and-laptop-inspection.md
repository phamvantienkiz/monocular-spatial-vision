# Hướng Dẫn Kỹ Thuật: Web HUD & Giám Sát Trực Quan Từ Laptop

> **Layer:** Implementation Layer (`docs/implementation/release-1/guide/03-web-hud-and-laptop-inspection.md`)  
> **Release:** Release 1 (Phase 1 Sandbox)  
> **Mục tiêu:** Giải quyết bài toán giám sát thị giác trên máy tính nhúng Headless (không màn hình)  

---

## 1. Trả Lời Cốt Lõi: "UI HUD Xem Ở Đâu? Xem Bằng Cách Nào?"

> [!IMPORTANT]
> **Jetson AGX Xavier là máy tính nhúng chạy Headless (không cắm màn hình). UI HUD không phải là cửa sổ phần mềm cài trên Jetson, mà là một Web Dashboard được Jetson phục vụ qua mạng để Developer xem trực tiếp trên TRÌNH DUYỆT CỦA LAPTOP!**

Không cần cài đặt X11 Forwarding hay VNC (vốn rất chậm chạp và giật lag khi truyền video độ phân giải cao). Toàn bộ quá trình kiểm nghiệm thị giác diễn ra qua trình duyệt web trên Laptop của bạn:

```
[ Raspberry Pi 3 ]  ──(TCP Socket 9876: Raw Frames + IMU)──>  [ Jetson AGX Xavier ]
                                                                      │
                                                       (FastAPI Web Server :8000)
                                                                      │
                                                     (Mạng LAN / WiFi / Ethernet)
                                                                      ▼
                                                       [ Laptop của Developer ]
                                                    Mở trình duyệt Chrome/Firefox:
                                                    http://192.168.1.20:8000/hud
```

---

## 2. Các Thành Phần Trực Quan Trên Web HUD

Khi truy cập `http://<jetson_ip>:8000/hud` từ Laptop, giao diện HTML5 Canvas hiển thị 4 vùng chức năng chuyên biệt:

```
+-----------------------------------------------------------------------------------------+
|  MONOCULAR SPATIAL VISION — OPERATOR HUD                          [ONLINE: 29.8 FPS]   |
+-----------------------------------------------------------+-----------------------------+
|                                                           | TELEMETRY STATS (WebSocket) |
|  [ VÙNG 1: CAMERA LIVE FEED (MJPEG STREAM) ]              | --------------------------- |
|                                                           | Pitch (θ):       12.48°     |
|   +-----------------------+                               | Roll (φ):        -0.12°     |
|   | person (0.92)         |                               | Camera Height:    0.285 m   |
|   |                       |                               | Ingest FPS:       30.0 FPS  |
|   |   [3D Wireframe Box]  |                               | Inference Time:   14.2 ms   |
|   |                       |                               | E2E Latency:      38.5 ms   |
|   +-----------*-----------+                               |                             |
|          (Z: 1.84m)                                       | DETECTED OBJECTS (2)        |
|                                                           | --------------------------- |
|  * Chấm đỏ #EF4444: Điểm đáy tiếp xúc mặt sàn             | #1: person                  |
|  * Khung xanh: 3D Bounding Box chiếu phối cảnh            |   Pos:  [0.15, 0.02, 1.84]m |
|                                                           |   Size: [0.45, 0.50, 1.65]m |
+-----------------------------------------------------------+-----------------------------+
|  [ VÙNG 2: BIRD'S EYE VIEW (BEV 2D CANVAS) ]              | [ VÙNG 3: LASER BENCHMARK ] |
|                                                           | --------------------------- |
|                Z = 3.0m -------------------               | Nhập khoảng cách laser thực:|
|                           [ Obj 2: Chair ]                | [ 1.825 ] mét   [CẬP NHẬT]  |
|                Z = 2.0m -------------------               |                             |
|                     [ Obj 1: Person ]                     | Khoảng cách đo:    1.840 m  |
|                Z = 1.0m -------------------               | Sai số tuyệt đối:  0.015 m  |
|                         ▲                                 | Sai số tương đối:  0.82%    |
|                      [CAMERA]                             | Kết luận: [ PASS (<= 5%) ]  |
+-----------------------------------------------------------+-----------------------------+
```

### Chi tiết kỹ thuật từng vùng:
1. **Vùng 1 (Camera Live Feed):**
   - Nạp trực tiếp từ thẻ `<img src="/api/v1/stream/live">` nhận luồng multipart MJPEG.
   - Hình ảnh đã được GPU Jetson vẽ đè sẵn: Mặt nạ phân đoạn màu bán trong suốt, điểm đỏ tiếp xúc sàn $(u, v)$ và khung dây 3D Wireframe.
2. **Vùng 2 (Bird's Eye View - BEV Canvas):**
   - Một thẻ HTML5 `<canvas>` kích thước $400 \times 300$ được vẽ lại bằng JavaScript ở tần số $30\text{Hz}$.
   - Tọa độ $[X, Z]$ của vật thể nhận từ WebSocket được ánh xạ lên lưới tọa độ 2D từ trên cao nhìn xuống, giúp kỹ sư quan sát trực quan vị trí vật thể tương đối so với camera.
3. **Vùng 3 (Laser Ground Truth Verification Panel):**
   - Kỹ sư dùng thước laser Bosch GLM chiếu vào chân vật thể, đọc giá trị (ví dụ `1.825m`) và gõ vào ô nhập trên Web HUD.
   - Trình duyệt tự động lấy tọa độ $Z_{\text{pred}}$ của vật thể tương ứng, tính:
     $$\text{Absolute Error} = |1.840 - 1.825| = 0.015\text{m}$$
     $$\text{AbsRel Error} = \frac{0.015}{1.825} \times 100\% = 0.82\%$$
   - Hiển thị nhãn **PASS** (màu xanh lá) nếu $\le 5.0\%$, **FAIL** (màu đỏ) nếu $> 5.0\%$.

---

## 3. Các Công Cụ Kiểm Tra Thay Thế Cho Developer Trên Laptop

Ngoài việc xem Web HUD qua trình duyệt, developer có thể dùng các công cụ sau ngay trên máy trạm của mình:

### 3.1. Truy cập Swagger UI chuẩn OpenAPI
- Mở trên Laptop: `http://192.168.1.20:8000/docs`
- Cho phép test gọi thử các API:
  - `GET /health`: Kiểm tra Jetson có online không, trạng thái GPU CUDA và VRAM.
  - `GET /api/v1/telemetry`: Lấy JSON telemetry mới nhất của 1 frame.
  - `POST /api/v1/benchmark/record`: Gửi mẫu dữ liệu laser vào cơ sở dữ liệu đối chuẩn.

### 3.2. Cửa Sổ Xem Nhanh Bằng Python OpenCV Trên Laptop (Nếu Không Thích Dùng Trình Duyệt)
Nếu bạn thích cửa sổ desktop native hơn trình duyệt web, chạy script sau trên Laptop:
```bash
python tools/laptop/live_hud_viewer.py --stream-url http://192.168.1.20:8000/api/v1/stream/live
```
Script sẽ mở cửa sổ `cv2.imshow` hiển thị video với độ trễ thấp nhất có thể.
