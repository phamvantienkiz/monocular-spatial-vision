# Hướng Dẫn Kỹ Thuật: Raspberry Pi 3 Setup, Audit, Capture & Network Streaming

> **Layer:** Implementation Layer (`docs/implementation/release-1/guide/01-pi3-capture-and-streaming-guide.md`)  
> **Release:** Release 1 (Phase 1 Sandbox)  
> **Target Hardware:** Raspberry Pi 3 Model B+ (Broadcom BCM2837B0, Quad-core Cortex-A53, 1GB LPDDR2 SDRAM)  
> **Sensors:** Digilent Pcam 5C (OmniVision OV5640 MIPI CSI-2) + IMU MPU6050 (I2C)

---

## 1. Kết Nối Phần Cứng (Wiring & Pinout)

### 1.1. Sơ đồ cắm cáp Pcam 5C (MIPI CSI-2)
1. **Cổng CSI trên Pi 3:** Nằm giữa cổng HDMI và cổng âm thanh 3.5mm (không nhầm với cổng DSI dành cho màn hình LCD).
2. **Chiều cắm cáp 15-pin FFC:**
   - Dùng hai ngón tay nhẹ nhàng nhấc thanh khóa nhựa màu đen/trắng lên.
   - Luồn cáp FFC vào khe cắm: **Mặt chân tiếp xúc đồng hướng về phía cổng HDMI**, mặt nhựa màu xanh/đen hướng về phía cổng Ethernet/USB.
   - Nhấn đều hai đầu thanh khóa xuống để cố định chặt cáp.

### 1.2. Sơ đồ nối dây cảm biến IMU MPU6050 (I2C)
Module MPU6050 giao tiếp qua bus I2C1 của Raspberry Pi 3:

| Chân MPU6050 | Chân Raspberry Pi 3 (Physical Pin) | Chức năng (GPIO Name) | Lưu ý kỹ thuật |
| :--- | :--- | :--- | :--- |
| **VCC** | **Pin 1** | `3.3V Power` | Tuyệt đối **không** nối vào 5V (tránh hỏng bus I2C 3.3V của SoC Pi) |
| **GND** | **Pin 6** (hoặc Pin 9, 14, 20) | `Ground` | Nối chung mass |
| **SDA** | **Pin 3** | `GPIO 2 (I2C1 SDA)` | Có sẵn pull-up 1.8kΩ trên board Pi |
| **SCL** | **Pin 5** | `GPIO 3 (I2C1 SCL)` | Có sẵn pull-up 1.8kΩ trên board Pi |
| **AD0** | Nối vào **GND** (hoặc để trống) | Địa chỉ I2C = `0x68` | Nếu nối lên 3.3V thì địa chỉ là `0x69` |

---

## 2. Truy Cập SSH & Kiểm Tra Hệ Thống (System Environment Audit)

### 2.1. Xác định địa chỉ IP và đăng nhập SSH từ Laptop
Từ máy tính Laptop (kết nối cùng mạng WiFi hoặc cắm cáp Ethernet vào Pi 3):
```bash
# 1. Tìm IP của Pi 3 qua lệnh ping mDNS
ping raspberrypi.local

# Hoặc quét mạng LAN qua lệnh arp (Windows PowerShell / Linux / macOS)
arp -a | grep -i "b8-27-eb\|dc-a6-32\|e4-5f-01"

# 2. Đăng nhập SSH vào Pi 3
ssh pi@192.168.1.50   # Thay bằng IP thực tế của Pi 3
# (Mặc định tài khoản: pi / raspberry hoặc tài khoản bạn đã tạo trong Raspberry Pi Imager)
```

### 2.2. Kiểm tra chi tiết phiên bản OS & Kiến trúc nhân (Kernel Audit)
Sau khi đã vào terminal của Pi 3:
```bash
# 1. Kiểm tra phiên bản hệ điều hành Linux
cat /etc/os-release
# Ghi nhận: Debian GNU/Linux 11 (Bullseye) hay Debian 12 (Bookworm)

# 2. Kiểm tra kiến trúc nhân (32-bit armv7l hay 64-bit aarch64)
uname -a
uname -m
# 32-bit: armv7l
# 64-bit: aarch64 (khuyến nghị cho hiệu năng tối đa)

# 3. Kiểm tra tình trạng throttling phần cứng và nhiệt độ CPU
vcgencmd get_throttling
# Kết quả 'throttled=0x0' -> Nguồn điện tốt, không bị sụt áp, nhiệt độ ổn định.
# Nếu khác 0x0 (như 0x50000 hoặc 0x50005) -> Cần đổi củ sạc 5V/2.5A và tản nhiệt.
vcgencmd measure_temp

# 4. Kiểm tra RAM và phân vùng Swap
free -h
# Pi 3 có tổng RAM 1GB (khoảng 920MB khả dụng). Swap mặc định thường là 100MB.

# 5. Kiểm tra phiên bản Python toàn cục
python3 --version
which python3
pip list
```

---

## 3. Dọn Dẹp Rác & Tối Ưu Hóa Hệ Thống Headless (Housekeeping)

Vì Raspberry Pi 3 có tài nguyên hạn chế (1GB RAM, 4 lõi Cortex-A53), ta cần dọn dẹp và tối ưu hóa hệ thống để dành trọn vẹn RAM/CPU cho tác vụ capture và stream video:

```bash
# 1. Cập nhật danh mục gói và dọn dẹp các thư viện mồ côi
sudo apt-get update
sudo apt-get autoremove -y
sudo apt-get clean

# 2. Tắt các dịch vụ nền không dùng cho Mobile Robot
# Tắt Bluetooth daemon (nếu không dùng)
sudo systemctl stop bluetooth
sudo systemctl disable bluetooth
sudo systemctl stop hciuart
sudo systemctl disable hciuart

# Tắt dịch vụ in ấn CUPS (nếu có cài trên bản Desktop)
sudo systemctl stop cups 2>/dev/null || true
sudo systemctl disable cups 2>/dev/null || true

# 3. Chuyển sang khởi động chế độ Console (Tắt Desktop GUI để tiết kiệm ~200MB RAM)
sudo systemctl set-default multi-user.target

# 4. (Tùy chọn) Tăng Swap tạm thời lên 1GB để tránh lỗi OOM khi cài thư viện Python
sudo dphys-swapfile swapoff
sudo sed -i 's/CONF_SWAPSIZE=100/CONF_SWAPSIZE=1024/' /etc/dphys-swapfile
sudo dphys-swapfile setup
sudo dphys-swapfile swapon
free -h
```

---

## 4. Tạo Không Gian Làm Việc, Clone Repo & Thiết Lập Môi Trường Ảo Cô Lập

Tuân thủ nghiêm ngặt quy định tại [AGENTS.md](file:///E:/UIT/monocular-spatial-vision/AGENTS.md): **Tuyệt đối không cài đặt gói pip vào môi trường toàn cục (system environment)**.

```bash
# 1. Cài đặt các công cụ phát triển cơ bản và thư viện hệ thống
sudo apt-get install -y git python3-venv python3-pip i2c-tools v4l-utils libv4l-dev

# 2. Phân quyền truy cập phần cứng I2C và Camera cho user hiện tại (tránh phải dùng sudo khi chạy code)
sudo usermod -aG video,i2c $USER

# 3. Tạo thư mục làm việc và Clone repo về Pi 3
mkdir -p ~/workspaces
cd ~/workspaces

# Clone repo từ Git (sử dụng link repo của dự án)
git clone https://github.com/<your-org>/monocular-spatial-vision.git
cd monocular-spatial-vision

# 4. Khởi tạo môi trường ảo Python biệt lập (.venv)
python3 -m venv .venv
source .venv/bin/activate

# Xác nhận đường dẫn Python trỏ chính xác vào .venv
which python
# Kết quả mong đợi: /home/pi/workspaces/monocular-spatial-vision/.venv/bin/python

# 5. Cài đặt các thư viện cần thiết trong môi trường ảo
pip install --upgrade pip setuptools wheel
cd services/pi_capture_agent
pip install -e .
# Hoặc cài đặt thủ công:
pip install opencv-python-headless smbus2 pyyaml numpy
```

---

## 5. Cấu Hình Driver Nhân & Device Tree Overlay

### 5.1. Kích hoạt I2C và nạp Overlay OV5640
Raspberry Pi cần nạp Device Tree Overlay để nhận diện Pcam 5C (chip OmniVision OV5640) qua bus MIPI CSI:

```bash
# 1. Kích hoạt I2C phần cứng bằng raspi-config
sudo raspi-config nonint do_i2c 0

# 2. Chỉnh sửa tệp cấu hình bootloader:
# Trên Debian Bookworm (mới):
# sudo nano /boot/firmware/config.txt
# Trên Debian Bullseye / Buster (cũ):
# sudo nano /boot/config.txt

CONFIG_FILE="/boot/firmware/config.txt"
[ ! -f "$CONFIG_FILE" ] && CONFIG_FILE="/boot/config.txt"

sudo bash -c "cat >> $CONFIG_FILE" << 'EOF'

# --- Monocular Spatial Vision Sensor Configuration ---
dtparam=i2c_arm=on
dtoverlay=ov5640
# Cấp phát 128MB RAM cho GPU VideoCore để xử lý camera mượt mà
gpu_mem=128
EOF

# 3. Khởi động lại Raspberry Pi 3 để kernel áp dụng Device Tree mới
sudo reboot
```

---

## 6. Bộ Lệnh Kiểm Tra Phần Cứng (Sanity Checks Sau Khi Reboot)

Sau khi Pi 3 khởi động lại, SSH lại vào terminal (`ssh pi@<pi_ip>`) và chạy các kiểm tra phần cứng cấp thấp:

### 6.1. Kiểm tra cảm biến IMU MPU6050 qua I2C
```bash
i2cdetect -y 1
```
**Kết quả mong đợi:**
```text
     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
00:                         -- -- -- -- -- -- -- -- 
10: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
20: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
30: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
40: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
50: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
60: -- -- -- -- -- -- -- -- 68 -- -- -- -- -- -- -- 
70: -- -- -- -- -- -- -- --                         
```
* Số `68` xuất hiện tại hàng 60 cột 8 $\to$ **Cảm biến MPU6050 kết nối thành công!**
* Nếu hiển thị toàn `--` $\to$ Kiểm tra lại 4 dây SDA, SCL, VCC (3.3V), GND.

### 6.2. Kiểm tra driver Camera Pcam 5C (OV5640)
```bash
# 1. Kiểm tra kernel log nạp chip OV5640
dmesg | grep -i ov5640
# Kết quả mong đợi: ov5640 10-003c: OV5640 probed successfully (hoặc ov5640 driver bound)

# 2. Liệt kê các node video
v4l2-ctl --list-devices
# Kết quả mong đợi xuất hiện:
# bcm2835-unicam (platform:unicam-v4l2):
#     /dev/video0

# 3. Kiểm tra các định dạng nén phần cứng và phân giải
v4l2-ctl -d /dev/video0 --list-formats-ext
# Xác nhận hỗ trợ định dạng 'MJPG' hoặc 'YUYV' tại 1280x720 @ 30fps
```

---

## 7. Các Bước Kiểm Nghiệm Phần Mềm Bằng `pi_capture_agent.cli`

Kích hoạt môi trường ảo trên Pi 3:
```bash
cd ~/workspaces/monocular-spatial-vision
source .venv/bin/activate
cd services/pi_capture_agent
```

### Nấc 1: Tự động chuẩn đoán toàn diện phần cứng (`--mode diag`)
```bash
python -m pi_capture_agent.cli --mode diag
```
CLI sẽ tự động:
- Đọc thanh ghi `WHO_AM_I` (0x75) của MPU6050 (kỳ vọng giá trị `0x68`).
- Khởi tạo bus I2C và đọc mẫu gia tốc đầu tiên.
- Mở node `/dev/video0`, thử đọc 5 frames camera và tính toán FPS thực tế.
- Báo cáo kết quả: `[SUCCESS] All hardware interfaces operational.`

### Nấc 2: Chụp ảnh đơn ra file (`--mode snapshot`)
```bash
python -m pi_capture_agent.cli --mode snapshot --output ./test_frame.jpg
```
Ảnh được lưu vào `./test_frame.jpg` với độ phân giải $1280 \times 720$.

### Nấc 3: Mở HTTP Preview Server trên Pi 3 (`--mode preview`)
Nếu không cắm màn hình vào Pi 3, hãy khởi chạy chế độ preview:
```bash
python -m pi_capture_agent.cli --mode preview --preview-port 8080
```
Từ trình duyệt trên Laptop, mở:
```text
http://<ip_pi_3>:8080/preview
```
Bạn sẽ thấy hình ảnh camera trực tiếp được cập nhật liên tục để căn chỉnh tiêu cự, góc chúc và ánh sáng phòng thí nghiệm.

### Nấc 4: Kiểm tra đọc dữ liệu góc nghiêng IMU (`--mode test-imu`)
```bash
python -m pi_capture_agent.cli --mode test-imu
```
Terminal in ra:
```text
[IMU-TEST] Ax: +0.012g | Ay: +0.218g | Az: +0.975g | Pitch (theta): 12.61° | Roll (phi): -0.15°
[IMU-TEST] Ax: +0.011g | Ay: +0.217g | Az: +0.976g | Pitch (theta): 12.58° | Roll (phi): -0.12°
```
Khi dùng tay nghiêng giá đỡ camera lên/xuống, giá trị Pitch thay đổi tức thời mà không có độ trễ.

### Nấc 5: Stream luồng nhị phân 36-byte về Laptop (`--mode stream`)
1. **Trên Laptop:** Khởi động backend ingest:
   ```bash
   python tools/laptop/mock_ingest_server.py --port 9876
   # Hoặc khởi động trọn bộ FastAPI Backend:
   uvicorn services.backend.app.main:app --host 0.0.0.0 --port 8000
   ```
2. **Trên Raspberry Pi 3:** Bắt đầu stream tới IP Laptop:
   ```bash
   python -m pi_capture_agent.cli --mode stream --host <IP_LAPTOP> --port 9876
   ```
3. **Mở trình duyệt trên Laptop:** `http://localhost:8000/hud` để quan sát toàn bộ Camera Live Feed, 3D Attitude Gauge và số liệu telemetry thời gian thực!

