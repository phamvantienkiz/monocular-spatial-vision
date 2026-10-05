# UI & Telemetry Visualization Specification — Release 1

> **Layer:** Implementation Layer (`docs/implementation/release-1/frontend/ui-spec.md`)  
> **Release:** Release 1 (Phase 1 Sandbox)  
> **Status:** Approved Baseline  

---

## 1. Operator Telemetry HUD Layout

Giao diện giám sát vận hành thời gian thực phục vụ kỹ sư trong quá trình kiểm nghiệm thực địa được bố trí như sau:

```
+-------------------------------------------------------------------------------+
| MONOCULAR SPATIAL VISION — OPERATOR HUD                          [ONLINE: 30 FPS] |
+-------------------------------------------------------+-----------------------+
|                                                       | TELEMETRY STATS       |
|  [ CAMERA OPTICAL FEED: 1280 x 720 ]                  | --------------------- |
|                                                       | Pitch (θ):  12.48°    |
|   +-------------------+                               | Roll (φ):   -0.12°    |
|   | person 0.94       |                               | Height (hc): 0.285 m  |
|   |                   |                               | Latency:    34.2 ms   |
|   |  [3D Box Wireframe]                               |                       |
|   |                   |                               | DETECTED OBJECTS (2)  |
|   +---------*---------+                               | --------------------- |
|        (Z: 1.82m)                                     | #1: person            |
|                                                       |   Pos: (0.15,0.02,1.82)|
|                                                       |   Size:(0.45,0.50,1.65)|
|                                                       | #2: chair             |
|                                                       |   Pos: (-0.60,0.1,2.40)|
+-------------------------------------------------------+-----------------------+
| BIRD'S EYE VIEW (BEV 2D GRID)                         | LASER GROUND TRUTH    |
| [ Grid scale: 0.5m/div | Max: 5.0m ]                  | Target GT:   1.815 m  |
| Camera: (0, 0) | Obj 1: (0.15, 1.82) | Obj 2: (-0.6, 2.4)| Abs Error:   0.005 m  |
|                                                       | AbsRel:      0.28%    |
+-------------------------------------------------------+-----------------------+
```

---

## 2. Rendering Rules & Interactions

- **Ground Contact Indicator:** Điểm `*` màu đỏ rực rỡ `#EF4444` tại đáy bounding box biểu diễn pixel tiếp xúc sàn dùng cho công thức IPM.
- **3D Wireframe Alignment:** Khung dây 3D chiếu phối cảnh ngược trực tiếp lên ảnh video phải khớp khít với biên bao thực tế của vật thể.
- **Color Coding:** Tuân thủ chuẩn token ngữ nghĩa tại [14-design-language.md](file:///E:/UIT/monocular-spatial-vision/docs/architecture/14-design-language.md).
