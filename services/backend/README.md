# Jetson AGX Xavier Perception Backend Service

> **Mô tả:** Dịch vụ trung tâm xử lý nhận luồng TCP, suy luận YOLOv8-seg (TensorRT FP16), giải toán IPM tính khoảng cách mặt sàn, dựng 3D Bounding Box và phục vụ Web HUD qua FastAPI.

## 1. Cài đặt môi trường trên Jetson hoặc Laptop
```bash
cd services/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## 2. Khởi chạy Dịch Vụ
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
- Mở tài liệu API: `http://localhost:8000/docs`
- Mở giao diện Operator HUD: `http://localhost:8000/hud`

## 3. Nhiệm vụ của Sinh viên (Student Implementation Tasks)
1. `app/services/ingest_service.py`: Mở TCP server port 9876, unpack header nhị phân 36-byte và duy trì Ring Buffer an toàn luồng (thread-safe).
2. `app/services/model_service.py`: Tải trọng số TensorRT `.engine`, thực hiện tiền xử lý (letterbox/normalize) và hậu xử lý trích xuất mask 2D.
3. `app/services/geometry_service.py`:
   - Trích xuất điểm đáy tiếp xúc mặt sàn $(u, v)$ từ mask.
   - Bù trừ góc nghiêng $\theta$ từ IMU và giải công thức IPM ra khoảng cách $Z$.
   - Tính toán tọa độ $[X, Y, Z]$ và kích thước $[L, W, H]$ trong không gian 3D.
4. `app/services/benchmark_service.py`: So khớp khoảng cách laser ground truth, tính sai số AbsRel và RMSE.
5. `app/api/v1/endpoints/stream.py`: Cung cấp luồng MJPEG stream `/api/v1/stream/live` có vẽ lớp phủ trực quan.
