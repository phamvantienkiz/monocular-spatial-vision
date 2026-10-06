# Architecture Layer — Navigation Map & System Invariants

> **Layer:** Architecture Layer (`docs/architecture/README.md`)  
> **Status:** Single Source of Truth (Living System)  
> **Rule:** ⛔ **NEVER divided by Release!** This layer captures living architectural truths and system invariants.

---

## 1. Architectural Map & Document Index

Tầng Kiến trúc (Architecture Layer) là **Nguồn Chân Lý Duy Nhất (Single Source of Truth)** cho toàn bộ hệ sinh thái kỹ thuật của dự án Monocular Spatial Vision. Mọi kỹ sư và AI Coding Agent bắt buộc phải tuân thủ nghiêm ngặt các bất biến hệ thống được ghi nhận trong các tài liệu dưới đây:

### Backend, Robotics & Core System Invariants
| Doc Index | Document Name | Purpose & Primary System Invariants |
| :--- | :--- | :--- |
| **01** | [01-system-context.md](file:///E:/UIT/monocular-spatial-vision/docs/architecture/01-system-context.md) | Phạm vi biên giới hệ thống, tác nhân (Actors), hệ thống ngoài (LiDAR, STM32, Laser GT). |
| **02** | [02-high-level-architecture.md](file:///E:/UIT/monocular-spatial-vision/docs/architecture/02-high-level-architecture.md) | Kiến trúc tổng quan 3 khối: Node thu nhận (Pi 3), Não bộ AI (Jetson AGX), Chuẩn Benchmark. |
| **03** | [03-service-architecture.md](file:///E:/UIT/monocular-spatial-vision/docs/architecture/03-service-architecture.md) | Phân rã các module/node: `pi_capture_agent`, `mono_ingest`, `mono_calib`, `depth_engine`, `object3d`. |
| **04** | [04-deployment-architecture.md](file:///E:/UIT/monocular-spatial-vision/docs/architecture/04-deployment-architecture.md) | Cấu hình triển khai: Linux V4L2/libcamera trên Pi 3, JetPack/CUDA/TensorRT trên Jetson AGX. |
| **05** | [05-data-architecture.md](file:///E:/UIT/monocular-spatial-vision/docs/architecture/05-data-architecture.md) | Cấu trúc dữ liệu khung hình (Frame Header, Timestamp int64 ns), Camera Matrix YAML, 3D BBox format. |
| **06** | [06-ai-architecture.md](file:///E:/UIT/monocular-spatial-vision/docs/architecture/06-ai-architecture.md) | Pipeline AI: 2D Detection/Seg (YOLOv8-seg), Metric Depth Net (Depth Anything V2), IPM geometry engine. |
| **07** | [07-security-architecture.md](file:///E:/UIT/monocular-spatial-vision/docs/architecture/07-security-architecture.md) | Chính sách an ninh mạng cục bộ, quản lý SSH keys, phân quyền truy cập camera và dữ liệu log. |
| **08** | [08-integration-architecture.md](file:///E:/UIT/monocular-spatial-vision/docs/architecture/08-integration-architecture.md) | Chuẩn tích hợp: Socket truyền stream, giao thức ROS 2 Foxy, custom messages, FastDDS QoS. |
| **09** | [09-design-principles.md](file:///E:/UIT/monocular-spatial-vision/docs/architecture/09-design-principles.md) | Nguyên tắc Clean Code, SOLID, xử lý lỗi tường minh, zero silent failures, cấu trúc module độc lập. |
| **10** | [10-folder-structure.md](file:///E:/UIT/monocular-spatial-vision/docs/architecture/10-folder-structure.md) | Bất biến cấu trúc thư mục repo, ranh giới giữa source code, configs, tests và documentation. |

### Visualization & Telemetry Interface
| Doc Index | Document Name | Purpose & Primary System Invariants |
| :--- | :--- | :--- |
| **11** | [11-frontend-system-design.md](file:///E:/UIT/monocular-spatial-vision/docs/architecture/11-frontend-system-design.md) | Thiết kế hệ thống hiển thị giám sát telemetry, kiến trúc RViz2 plugins và Web Telemetry Viewer. |
| **12** | [12-design-system.md](file:///E:/UIT/monocular-spatial-vision/docs/architecture/12-design-system.md) | Quy cách các component hiển thị: Bounding Box 2D/3D wireframe, Pointcloud depth overlay, chỉ báo telemetry. |
| **13** | [13-frontend-architecture.md](file:///E:/UIT/monocular-spatial-vision/docs/architecture/13-frontend-architecture.md) | Quản lý trạng thái client, đồng bộ khung hình/dữ liệu góc IMU, cơ chế render thời gian thực. |
| **14** | [14-design-language.md](file:///E:/UIT/monocular-spatial-vision/docs/architecture/14-design-language.md) | Hệ thống token thiết kế, bảng màu phân loại vật thể (Class Colors), thang kích thước hộp bao 3D. |

### Architectural Decision Records
- [Architecture Decision Records Index (ADR)](file:///E:/UIT/monocular-spatial-vision/docs/architecture/adr/README.md)
  - [ADR-001: Phân tách Sandbox Nghiên cứu Độc lập & Kiến trúc Camera Đơn Pcam 5C](file:///E:/UIT/monocular-spatial-vision/docs/architecture/adr/ADR-001.md)

---

## 2. Invariant Rules for AI Coding Agents

1. **Architecture Is Immutable without ADR:** Tuyệt đối không tự ý thay đổi các giao thức mạng, định dạng frame header, cấu trúc topic ROS 2 hoặc quy ước tọa độ chuẩn ($X$-phải, $Y$-xuống, $Z$-thẳng theo camera convention; $X$-trước, $Y$-trái, $Z$-lên theo robot convention) nếu chưa có ADR được duyệt.
2. **Every Code Change Must Cite Architecture Guardrails:** Mọi User Story trong `docs/implementation/{release}/backlog/stories/` phải trích dẫn trực tiếp các tài liệu kiến trúc tương ứng trước khi tiến hành code.
3. **Pure Markdown Invariant:** Mọi tài liệu trong `docs/architecture/` bắt buộc phải là Pure Markdown (`.md`) kèm sơ đồ Mermaid chuẩn, nghiêm cấm nhúng mã HTML/JS inline. Các giao diện trực quan standalone phải được đặt tại `docs/views/`.
