# 14 - Design Language & Semantic Color System

> **Layer:** Architecture Layer (`docs/architecture/14-design-language.md`)  
> **Status:** Single Source of Truth — Living Architecture  

---

## 1. Semantic Color Tokens for Object Classes

Bảng màu được chuẩn hóa nhằm tối ưu độ tương phản trên các điều kiện bề mặt sàn phòng lab (sàn gạch men sáng hoặc sàn thảm tối):

| Object Class | Hex Color Token | RGB Equivalent | Usage & Semantic Meaning |
| :--- | :--- | :--- | :--- |
| **Person / Pedestrian** | `#F59E0B` (Amber 500) | `rgb(245, 158, 11)` | Người đi bộ / Đối tượng ưu tiên an toàn cao nhất |
| **Chair / Stool** | `#3B82F6` (Blue 500) | `rgb(59, 130, 246)` | Ghế văn phòng / Vật cản tĩnh chân nhỏ |
| **Table / Desk** | `#10B981` (Emerald 500) | `rgb(16, 185, 129)` | Bàn làm việc / Vật cản có mặt phẳng lơ lửng |
| **Obstacle (General)** | `#EC4899` (Pink 500) | `rgb(236, 72, 153)` | Các vật thể không xác định / Hộp carton |
| **Ground Contact Point** | `#EF4444` (Red 500) | `rgb(239, 68, 68)` | Điểm neo chân tiếp xúc mặt sàn của thuật toán |
| **Laser Ground Truth** | `#8B5CF6` (Violet 500) | `rgb(139, 92, 246)` | Dữ liệu đối chuẩn thực địa từ thước laser |

---

## 2. Typography & HUD Text Hierarchy

- **Font Family:** Phông chữ đơn cách (Monospace) cho các chỉ số đo lường: `JetBrains Mono`, `Fira Code`, hoặc `ui-monospace`.
- **Text Sizes:**
  - Nhãn đối tượng trên hộp bao 2D: `12px bold` với nền đen mờ ($\alpha = 0.6$).
  - Chỉ số cự ly 3D: `14px bold` với chữ viền đen tăng cường tương phản quang học.
  - Thông số HUD góc màn hình (FPS, Latency, Pitch): `11px regular`.
