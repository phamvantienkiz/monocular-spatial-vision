# 12 - Visualization Design System & UI Components

> **Layer:** Architecture Layer (`docs/architecture/12-design-system.md`)  
> **Status:** Single Source of Truth — Living Architecture  

---

## 1. Visual Component Catalog

Hệ thống thành phần hiển thị trực quan được tiêu chuẩn hóa cho cả RViz2 Marker và Web Canvas 2D/3D:

| Component Code | Component Name | Description & Rendering Rules |
| :--- | :--- | :--- |
| **CMP-01** | `BBox2DOverlay` | Khung hình chữ nhật 2D bao quanh vật thể, viền $2\text{px}$, nhãn class kèm chỉ số confidence (ví dụ: `person 0.92`). |
| **CMP-02** | `InstanceMaskOverlay` | Lớp mặt nạ phân đoạn màu bán trong suốt ($\alpha = 0.35$) phủ chính xác lên pixel của vật thể. |
| **CMP-03** | `GroundContactDot` | Điểm tròn bán kính $5\text{px}$ màu đỏ đậm `#EF4444` đánh dấu vị trí chân tiếp xúc sàn được thuật toán lựa chọn. |
| **CMP-04** | `BBox3DWireframe` | Khối lập phương 3D gồm 12 cạnh wireframe với 4 cạnh chân đế phân biệt màu sắc so với 4 cạnh mặt trên. |
| **CMP-05** | `BEVGridCanvas` | Lưới tọa độ nhìn từ trên cao xuống (Bird's Eye View) với các vòng tròn đồng tâm $1\text{m}, 2\text{m}, 3\text{m}, 4\text{m}$. |
| **CMP-06** | `TelemetryBadge` | Khối thông số HUD góc trên màn hình hiển thị FPS, thời gian suy luận (Latency) và góc nghiêng IMU. |

---

## 2. 3D Wireframe Rendering Convention

Hộp bao 3D được xác định bởi 8 đỉnh trong không gian camera:
- Mặt đáy ($Z = Z_{\text{ground}}$, tiếp xúc sàn): Đỉnh 0, 1, 2, 3 được vẽ bằng nét liền đậm màu xanh lam `#3B82F6`.
- Mặt đỉnh ($Y = Y_{\text{ground}} - H$, đỉnh vật thể): Đỉnh 4, 5, 6, 7 được vẽ bằng nét liền màu ngọc lam `#06B6D4`.
- 4 trụ đứng nối đáy và đỉnh: Được vẽ bằng nét đứt mỏng để tạo cảm giác chiều sâu không gian quang học.
