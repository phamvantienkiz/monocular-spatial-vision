# Migration & Setup Guide — Release 1 Sandbox

> **Layer:** Implementation Layer (`docs/implementation/release-1/migration.md`)  
> **Release:** Release 1 (Phase 1 Sandbox)  
> **Status:** Approved Baseline  

---

## 1. Environment Setup & Dependency Isolation

Tuân thủ nghiêm ngặt quy định tại `AGENTS.md`, mọi quá trình cài đặt phần mềm và thư viện đều phải được cách ly hoàn toàn:

### 1.1. Setup on Jetson AGX Xavier
```bash
# Di chuyển vào thư mục dự án
cd monocular-spatial-vision

# Khởi tạo môi trường ảo Python cục bộ bằng uv hoặc venv
uv venv .venv
source .venv/bin/activate

# Cài đặt các phụ thuộc bắt buộc
uv pip install -r requirements.txt

# Kiểm tra GPU TensorRT & CUDA runtime
python -c "import tensorrt; print('TensorRT Version:', tensorrt.__version__)"
python -c "import torch; print('CUDA Available:', torch.cuda.is_available())"
```

### 1.2. Setup on Raspberry Pi 3
```bash
# Kích hoạt giao tiếp I2C và Camera trên Pi 3
sudo raspi-config nonint do_i2c 0
sudo raspi-config nonint do_camera 0

# Cấu hình Device Tree Overlay cho OV5640 nếu dùng V4L2 mainline
# Thêm vào /boot/config.txt: dtoverlay=ov5640

# Khởi tạo virtualenv trên Pi 3
python3 -m venv .venv
source .venv/bin/activate
pip install opencv-python-headless smbus2
```

---

## 2. Hardware Test Rig Alignment & Calibration Migration

Trước khi tiến hành đo đạc benchmark, kỹ sư phải tuân thủ trình tự di chuyển và cân chỉnh cơ khí:
1. Đặt giá đỡ kiểm thử tại vị trí cố định trên sàn phẳng phòng lab.
2. Dùng thước bọt nước li-vô kiểm tra độ thăng bằng ngang (đảm bảo góc roll $\phi \approx 0^\circ$).
3. Dùng thước cuộn đo chính xác chiều cao tâm thấu kính tới sàn $h_c$ (ghi nhận vào `configs/calib_pcam5c.yaml`).
4. Bật nguồn module Pi 3 và kiểm tra góc pitch tĩnh $\theta$ báo về từ cảm biến MPU6050, ghi nhận độ lệch nếu có.
