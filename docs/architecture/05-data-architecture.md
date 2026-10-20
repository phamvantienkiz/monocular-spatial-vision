# 05 - Data Architecture & Schema Standards

> **Layer:** Architecture Layer (`docs/architecture/05-data-architecture.md`)  
> **Status:** Single Source of Truth — Living Architecture  

---

## 1. Network Streaming Binary Frame Header (40-Byte Wire Format `>HHIQffIIII`)

Mọi khung hình truyền từ Raspberry Pi 3 (`services/pi_capture_agent/` bản Python hoặc `services/pi_capture_agent_cpp/` bản C++17) sang Laptop / Jetson AGX Xavier đều được đóng gói theo cấu trúc nhị phân cố định **40 bytes** (Big-Endian network byte order, định dạng `struct` chuẩn `>HHIQffIIII`):

```
+--------------------------------------------------------------------------------+
| Offset 0..1:  MAGIC (2B, uint16)      | Offset 2..3:  VERSION (2B, uint16)     |
|               0x50 0x43 ('P', 'C')    |               0x00 0x01 (v1)           |
+--------------------------------------------------------------------------------+
| Offset 4..7:  FRAME_ID (4B, uint32)                                            |
|               Monotonically increasing frame sequence number                   |
+--------------------------------------------------------------------------------+
| Offset 8..15: TIMESTAMP_NS (8B, uint64)                                        |
|               Capture hardware timestamp in nanoseconds                        |
+--------------------------------------------------------------------------------+
| Offset 16..19: PITCH_DEG (4B, float32)| Offset 20..23: ROLL_DEG (4B, float32)  |
|                IEEE 754 Big-Endian    |                IEEE 754 Big-Endian     |
+--------------------------------------------------------------------------------+
| Offset 24..27: PAYLOAD_LEN (4B, uint32)                                        |
|                Exact byte length of the following JPEG payload                 |
+--------------------------------------------------------------------------------+
| Offset 28..31: WIDTH (4B, uint32)     | Offset 32..35: HEIGHT (4B, uint32)     |
|                e.g. 1280 (or 640)     |                e.g. 720 (or 360)       |
+--------------------------------------------------------------------------------+
| Offset 36..39: RESERVED (4B, uint32)                                           |
|                0x00000000 (Alignment & future flags)                           |
+--------------------------------------------------------------------------------+
| Offset 40..40+PAYLOAD_LEN: PAYLOAD (Compressed JPEG Image Bytes)               |
+--------------------------------------------------------------------------------+
```

### Invariants:
- **Tổng kích thước Header:** Chính xác **40 bytes** (`sizeof(PackedFrameHeader) == 40`, `struct.calcsize(">HHIQffIIII") == 40`).
- **`MAGIC`:** Giá trị cố định `0x5043` (`"PC"` - Pcam).
- **Truyền nguyên tử (Atomic Frame Transmission):** Một khi đã gửi byte đầu tiên của Header 40-byte trên kết nối TCP, bên gửi bắt buộc phải truyền đủ `40 + PAYLOAD_LEN` bytes trước khi gửi khung hình kế tiếp để không bao giờ làm lệch pha bộ đọc phía Ingest Server.

---

## 2. Calibration Parameter File Schema (`YAML`)

Thông số hiệu chuẩn nội suy và ngoại quan được chuẩn hóa và lưu trữ tại `configs/calib_pcam5c.yaml`:

```yaml
camera_info:
  camera_name: "pcam5c_ov5640"
  image_width: 1280
  image_height: 720
  distortion_model: "plumb_bob"

intrinsics:
  camera_matrix: # K
    rows: 3
    cols: 3
    data: [fx, 0.0, cx, 0.0, fy, cy, 0.0, 0.0, 1.0]
  distortion_coefficients: # D
    rows: 1
    cols: 5
    data: [k1, k2, p1, p2, k3]
  rectification_matrix: # R
    rows: 3
    cols: 3
    data: [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
  projection_matrix: # P
    rows: 3
    cols: 4
    data: [fx, 0.0, cx, 0.0, 0.0, fy, cy, 0.0, 0.0, 0.0, 1.0, 0.0]

extrinsics_ground:
  nominal_height_m: 0.285      # Chiều cao thấu kính tới sàn hc (m)
  nominal_pitch_deg: 12.5      # Góc chúc mặc định của camera (độ)
  nominal_roll_deg: 0.0        # Góc nghiêng ngang (độ)
  transform_base_to_camera:
    translation: [0.15, 0.0, 0.285] # [x_forward, y_left, z_up]
    rotation_rpy: [0.0, 0.218166, 0.0] # [roll, pitch, yaw] radians
```

---

## 3. 3D Object Detection & Bounding Box Data Structure

Đầu ra của module nhận thức được cấu trúc thành mảng các đối tượng 3D (`Object3DArray`):

```yaml
header:
  stamp: { sec: 1728100000, nanosec: 123456789 }
  frame_id: "camera_optical_frame"

objects:
  - object_id: 1
    class_id: 0
    class_name: "person"
    confidence: 0.89
    
    # 2D Bounding Box & Segmentation Contact
    bbox_2d: [ymin, xmin, ymax, xmax] # normalized [0, 1]
    lowest_ground_contact_px: [u, v]  # Pixel tiếp xúc sàn tính IPM
    
    # 3D Metric Spatial Estimation (Hệ tọa độ camera: X-phải, Y-xuống, Z-thẳng)
    position:
      x: 0.35  # meters
      y: 0.12  # meters
      z: 2.15  # meters (khoảng cách thực tế)
    
    dimensions:
      length: 0.45 # meters (chiều sâu dọc trục Z)
      width: 0.50  # meters (chiều rộng dọc trục X)
      height: 1.65 # meters (chiều cao dọc trục Y)
      
    orientation:
      yaw_rad: 0.05
      
    depth_source: "ipm_ground" # Các giá trị: "ipm_ground", "metric_net", "lidar_fusion"
    variance_z: 0.008          # Độ tin cậy ước lượng (phương sai)
```
