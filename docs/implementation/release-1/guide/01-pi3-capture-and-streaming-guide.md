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
# Lưu ý: Trên Debian 12 (Bookworm) & 13 (Trixie) với nhân kernel 6.x, vcgencmd cần chạy với sudo:
sudo vcgencmd get_throttling
# Hoặc kiểm tra trực tiếp qua sysfs của kernel:
cat /sys/devices/platform/soc/soc:firmware/get_throttled 2>/dev/null || true
# Kết quả mong đợi: 'throttled=0x0' (hoặc '0') -> Nguồn điện tốt, không bị sụt áp, không quá nhiệt.
# Nếu khác 0x0 (như 0x50000 hoặc 0x50005) -> Cần đổi nguồn 5V/2.5A và bổ sung tản nhiệt.
vcgencmd measure_temp

# 4. Kiểm tra RAM và phân vùng Swap
free -h
# Pi 3 Model B+ có 1GB LPDDR2 (khoảng 920MB hiển thị).
# Nếu Swap đã đạt ~1GB (919MiB khả dụng) như trường hợp của bạn, hệ thống đã sẵn sàng, không cần chỉnh swap thêm.

# 5. Kiểm tra phiên bản Python toàn cục & thư viện apt sẵn có
python3 --version
which python3
pip list
```

---

## 3. Dọn Dẹp Rác & Tối Ưu Hóa Hệ Thống Headless (Housekeeping)

Dựa trên kết quả audit thực tế trên Debian 13 (Trixie), hệ thống có một số dịch vụ nền và package Desktop gây hao tổn RAM và làm chậm khởi động. Hãy chạy các bước dọn dẹp sau:

```bash
# 1. Tắt dịch vụ cloud-init (thủ phạm ngốn 15-20 giây lúc boot và chiếm RAM nền trên Pi)
sudo systemctl stop cloud-init cloud-init-local cloud-config cloud-final 2>/dev/null || true
sudo systemctl disable cloud-init cloud-init-local cloud-config cloud-final 2>/dev/null || true
sudo mkdir -p /etc/cloud && sudo touch /etc/cloud/cloud-init.disabled

# 2. Gỡ bỏ các ứng dụng GUI Desktop và dịch vụ in ấn thừa thãi
sudo apt-get purge -y thonny cups cupshelpers 2>/dev/null || true

# 3. Tắt Bluetooth daemon và giao tiếp UART Bluetooth (nếu robot chỉ dùng Ethernet/WiFi)
sudo systemctl stop bluetooth hciuart 2>/dev/null || true
sudo systemctl disable bluetooth hciuart 2>/dev/null || true

# 4. Tắt Desktop GUI Display Manager (Chuyển hẳn sang chế độ Console Headless để giải phóng ~200MB RAM)
sudo systemctl set-default multi-user.target

# 5. Dọn dẹp package mồ côi và làm sạch cache apt
sudo apt-get autoremove -y --purge
sudo apt-get clean

# 6. Kiểm tra lại mức tiêu thụ RAM sau dọn dẹp
free -h
# Mức tiêu thụ RAM lý tưởng sau khi dọn dẹp ở trạng thái nghỉ: used ~ 80MB - 120MB.
```

---

## 4. Tạo Không Gian Làm Việc, Clone Repo & Thiết Lập Môi Trường Ảo Cô Lập

Tuân thủ nghiêm ngặt quy định tại [AGENTS.md](file:///E:/UIT/monocular-spatial-vision/AGENTS.md) và cơ chế PEP 668 (`EXTERNALLY-MANAGED`) trên Debian 13: **Tuyệt đối không chạy `pip install` thẳng vào Python toàn cục**.

> [!TIP]
> **Kinh nghiệm thực địa với ARMv7 (32-bit):** Trong `pip list` toàn cục của bạn đã có sẵn bản build `opencv 4.10.0` và `picamera2 0.3.37` được tối ưu phần cứng từ apt. Khi tạo virtual environment với cờ `--system-site-packages`, môi trường ảo sẽ kế thừa ngay lập tức thư viện OpenCV tối ưu này mà **không phải tốn hàng chục phút biên dịch lại từ mã nguồn trên vi xử lý Cortex-A53 của Pi 3**, đồng thời vẫn bảo đảm tính cô lập cho toàn bộ code và dependencies còn lại!

```bash
# 1. Cài đặt các công cụ phát triển cơ bản và tiện ích phần cứng
sudo apt-get install -y git python3-venv python3-pip i2c-tools v4l-utils libv4l-dev

# 2. Phân quyền truy cập phần cứng I2C và Camera cho user hiện tại (tránh phải dùng sudo khi chạy code)
sudo usermod -aG video,i2c $USER

# 3. Tạo thư mục làm việc và Clone repo về Pi 3
mkdir -p ~/workspaces
cd ~/workspaces

# Clone repo từ Git (chuyển sang branch dự án tương ứng, ví dụ branch 'jin')
git clone https://github.com/<your-org>/monocular-spatial-vision.git
cd monocular-spatial-vision
git checkout jin

# 4. Khởi tạo môi trường ảo Python kế thừa site-packages tối ưu
python3 -m venv --system-site-packages .venv
source .venv/bin/activate

# Xác nhận đường dẫn Python trỏ chính xác vào .venv
which python
# Kết quả mong đợi: /home/r3b/workspaces/monocular-spatial-vision/.venv/bin/python

# 5. Cài đặt các thư viện cần thiết trong môi trường ảo
pip install --upgrade pip setuptools wheel
cd services/pi_capture_agent
pip install -e .
# Hoặc cài đặt thủ công:
pip install pyyaml smbus2
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

# --- Monocular Spatial Vision Sensor Configuration ---
# 1. Tắt tự động nhận diện camera chính hãng để nhường quyền điều khiển cho overlay ov5640
camera_auto_detect=0

# 2. Bật I2C cho MPU6050 (i2c_arm) và I2C cho Camera CSI (i2c_vc)
dtparam=i2c_arm=on
dtparam=i2c_vc=on

# 3. Kích hoạt dồn kênh I2C và xung nhịp clock 24MHz cho cổng camera CSI
dtoverlay=i2c0mux-enable
dtoverlay=cam1clk-enable

# 4. TẠO THIẾT BỊ OV5640 TRƯỚC (sinh ra node /soc/i2c0mux/i2c@1/ov5640@3c)
dtoverlay=ov5640

# 5. CẤP NGUỒN CHO OV5640 SAU (gắn cam1_regulator/PWUP vào node ov5640 vừa tạo)
# LƯU Ý BẮT BUỘC: ov5640-supply PHẢI nằm SAU ov5640 trong config.txt!
dtoverlay=ov5640-supply

# 6. Cấp phát 128MB RAM cho GPU VideoCore để xử lý camera mượt mà
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

# 2. Liệt kê các node video do unicam tạo ra
v4l2-ctl --list-devices

# 3. Kiểm tra các định dạng nén và thô hỗ trợ
v4l2-ctl -d /dev/video0 --list-formats-ext
```

---

### 6.3. Khắc Phục Lỗi Thực Địa: `ov5640_write_reg: error: reg=3008, val=82`

Nếu `dmesg | grep -i ov5640` xuất hiện dòng lỗi:
```text
ov5640 10-003c: ov5640_write_reg: error: reg=3008, val=82
```
**Bản chất kỹ thuật chuẩn xác của lỗi:**
1. **Lệnh gửi:** Driver `ov5640` trong kernel gửi lệnh Software Reset (ghi giá trị `0x82` vào thanh ghi `0x3008` - `OV5640_REG_SYS_CTRL0`) ngay trong hàm `ov5640_probe()`.
2. **Nguyên nhân thất bại:** Chip Pcam 5C **không gửi lại tín hiệu ACK (I2C NACK / EIO)** trên bus I2C số 10.
3. **Hiểu lầm phổ biến về ký tự `UU`:**
   * Khi chạy `sudo i2cdetect -y 10`, bạn thấy `UU` tại `0x3c` $\to$ **Điều này KHÔNG CÓ NGHĨA là phần cứng đã thông!**
   * Ký tự `UU` (*Unit in Use*) chỉ biểu thị rằng Device Tree đã gán địa chỉ `0x3c` cho module kernel `ov5640`. Tiện ích `i2cdetect` khi thấy địa chỉ đã có driver chiếm giữ sẽ **tự động bỏ qua không phát xung thăm dò vật lý** và in thẳng chữ `UU`.
   * Do đó, dù cáp camera bị đứt hay rút ra hoàn toàn, `i2cdetect` vẫn sẽ hiển thị `UU` nếu overlay đã được nạp!

---

### Quy trình 4 bước cô lập và giải quyết triệt để lỗi:

#### Bước 1: Gỡ Driver để Thăm Dò Tín Hiệu Vật Lý Thực Tế
Để kiểm tra xem chip OV5640 trên bo Pcam 5C có thực sự có điện và trả lời xung I2C hay không, bạn cần gỡ module kernel để giải phóng địa chỉ `0x3c`:
```bash
# 1. Gỡ tạm thời driver ov5640 khỏi nhân
sudo rmmod ov5640

# 2. Bây giờ chạy i2cdetect sẽ gửi xung điện thực qua dây cáp:
sudo i2cdetect -y 10
```
* **Kịch bản A (Phần cứng TỐT):** Xuất hiện số `3c` tại hàng 30 cột c. $\to$ Phần cứng đã có điện, lỗi nằm ở thứ tự overlay hoặc clock MCLK trong cấu hình Device Tree.
* **Kịch bản B (Phần cứng MẤT ĐIỆN / HỞ MẠCH):** Toàn bộ bảng là `--` (kể cả ô `3c`). $\to$ **Khẳng định 100% cảm biến đang không có nguồn hoặc cáp cắm sai / lỏng chân.** Hãy chuyển ngay sang Bước 2!

#### Bước 2: Kiểm Tra & Cắm Lại Cáp FFC 15-pin (Nguyên nhân chiếm 85%)
1. Tắt nguồn Pi 3 hoàn toàn và rút adapter 5V:
   ```bash
   sudo poweroff
   ```
2. **Đầu cắm phía Digilent Pcam 5C:**
   - Đầu nối trên board Pcam 5C là dạng *bottom-load, top-contact*.
   - **Mặt chân tiếp xúc bằng kim loại/đồng phải hướng về phía MẶT BO MẠCH PCAM 5C** (mặt có linh kiện và ống kính).
   - Mặt nhựa gia cường màu xanh/đen hướng ra ngoài.
   - Nhẹ nhàng kéo khóa ngàm đen ra, đút cáp ngập sâu, thẳng góc và ấn đều hai bên ngàm khóa lại.
3. **Đầu cắm phía Raspberry Pi 3:**
   - Cổng CSI nằm giữa cổng HDMI và giắc 3.5mm.
   - **Mặt chân tiếp xúc bằng kim loại/đồng phải hướng về phía CỔNG HDMI**.
   - Mặt nhựa gia cường màu xanh hướng về phía giắc cắm âm thanh 3.5mm / cổng Ethernet.
4. **Kiểm tra chân 11 (`PWUP`) & chân 15 (`3V3`):**
   - Chân 11 (`PWUP` - Power Up) kích hoạt các IC hạ áp LDO (1.5V, 1.8V, 2.8V) trên board Pcam 5C.
   - Chân 15 cấp nguồn 3.3V chính từ Pi sang Pcam 5C.
   - Vì 2 chân này nằm ở mép ngoài của dải cáp 15 chân, chỉ cần cáp bị cắm lệch nghiêng 0.3mm là bo Pcam 5C sẽ mất hoàn toàn nguồn điện!

#### Bước 3: Kiểm Tra Nội Dung Overlays & Trạng Thái GPIO
Để xác định các overlay của bạn có điều khiển đúng chân nguồn `PWUP` và xung nhịp `MCLK 24MHz` hay không, chạy lệnh giải mã (decompile):
```bash
# Kiểm tra cấu trúc overlay OV5640 và nguồn:
dtc -I dtb -O dts /boot/firmware/overlays/ov5640.dtbo | head -n 45
dtc -I dtb -O dts /boot/firmware/overlays/ov5640-supply.dtbo | head -n 45

# Kiểm tra trạng thái các chân GPIO trong kernel debugfs:
sudo cat /sys/kernel/debug/gpio
```

#### Bước 4: Kiểm Tra Sau Khi Nạp Lại Driver
Sau khi kiểm tra cáp và bật máy lại:
```bash
# Nạp lại driver:
sudo modprobe ov5640

# Kiểm tra lại dmesg:
dmesg | grep -i ov5640
```
**Kết quả thành công mong đợi:**
Không còn xuất hiện dòng `ov5640_write_reg: error: reg=3008, val=82`. Thay vào đó sẽ là thông báo khởi tạo thành công hoặc xuất hiện subdevice gắn với unicam.

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

