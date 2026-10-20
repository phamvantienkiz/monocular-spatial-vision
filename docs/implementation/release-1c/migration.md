# Migration & Setup Guide — Release 1c Pure C/C++ Native

> **Layer:** Implementation Layer (`docs/implementation/release-1c/migration.md`)  
> **Release:** Release 1c (C/C++ Native Edge Capture & Perception Pipeline)  
> **Status:** Approved Baseline (Audited & Revised)  

---

## 1. Thiết Lập Môi Trường Cô Lập Tuyệt Đối (Zero System Pollution)

Tuân thủ nghiêm ngặt quy định tại [`AGENTS.md`](file:///E:/UIT/monocular-spatial-vision/AGENTS.md), dự án **tuyệt đối không cài đặt thư viện C++ vào `/usr/local/` và không tự ý sửa đổi các tệp cấu hình toàn cục của hệ điều hành** (như `/etc/dphys-swapfile`). Toàn bộ công cụ quản lý gói và sản phẩm biên dịch được đóng gói khép kín bên trong không gian làm việc của repository.

### 1.1. Bước 1: Kiểm Tra Quyền Truy Cập Phần Cứng & Bộ Nhớ Trên Raspberry Pi 3

Đảm bảo tài khoản người dùng (`pi` hoặc `r3b`) thuộc nhóm `video` và `i2c`, đồng thời kiểm tra nhanh dung lượng RAM/Swap khả dụng:

```bash
# 1. Kiểm tra nhóm quyền phần cứng (video, i2c)
groups
# Nếu chưa có video và i2c: sudo usermod -aG video,i2c $USER (sau đó đăng nhập lại)

# 2. Kiểm tra các công cụ biên dịch cơ bản của hệ thống (gcc, g++, cmake, media-ctl, v4l2-ctl)
g++ --version
cmake --version
v4l2-ctl --version
media-ctl -h | head -n 3

# 3. Kiểm tra RAM và Swap hiện có (Không cần sửa /etc/dphys-swapfile nếu Swap đã có sẵn ~1GB)
free -h
```

---

### 1.2. Bước 2: Khởi Tạo Môi Trường Ảo Bằng `uv` & Cài Đặt Conan 2.0 Cục Bộ

Chúng ta tận dụng môi trường ảo `.venv` tại thư mục gốc của dự án (được tạo bởi `uv`) để cài đặt công cụ `conan` mà không chạm tới Python hệ thống:

```bash
# Di chuyển vào thư mục gốc của dự án
cd ~/workspaces/monocular-spatial-vision

# Khởi tạo môi trường ảo biệt lập bằng uv (nếu chưa tạo)
uv venv .venv

# Cài đặt Conan 2.0 trực tiếp vào .venv
uv pip install conan

# Kích hoạt môi trường ảo
source .venv/bin/activate

# Kiểm tra đường dẫn và phiên bản conan
which conan
conan --version
```

---

### 1.3. Bước 3: Cấu Hình Cache Cục Bộ `CONAN_HOME` & Giới Hạn Luồng Biên Dịch

Mặc định Conan lưu cache tại `~/.conan2`. Để cô lập $100\%$ trong workspace của dự án và tránh tràn RAM $1\text{GB}$ của Pi 3 khi biên dịch:

```bash
# 1. Đặt biến môi trường CONAN_HOME trỏ vào thư mục .conan ngay trong repo
export CONAN_HOME="$(pwd)/.conan"

# 2. Tự động nhận diện cấu hình trình biên dịch của Raspberry Pi 3
conan profile detect --force

# 3. Giới hạn tối đa 2 luồng biên dịch trong Conan profile để bảo vệ RAM 1GB và thẻ nhớ microSD
if ! grep -q "tools.build:jobs" "$CONAN_HOME/profiles/default"; then
    printf "\n[conf]\ntools.build:jobs=2\n" >> "$CONAN_HOME/profiles/default"
fi
```

---

### 1.4. Bước 4: Cài Đặt Phụ Thuộc C++ & Biên Dịch Trong `services/pi_capture_agent_cpp/`

> [!IMPORTANT]
> Tệp `conanfile.txt` và `CMakeLists.txt` nằm tại thư mục dịch vụ `services/pi_capture_agent_cpp/`. Mọi lệnh cài đặt phụ thuộc C++ và biên dịch CMake đều thực hiện tại thư mục này (ưu tiên tải binary có sẵn từ Conan Center trước khi biên dịch từ source):

```bash
# 1. Di chuyển vào thư mục dịch vụ C++
cd ~/workspaces/monocular-spatial-vision/services/pi_capture_agent_cpp

# 2. Cài đặt phụ thuộc từ conanfile.txt vào thư mục build/
conan install . --output-folder=build --build=missing -s build_type=Release

# 3. Cấu hình CMake sử dụng toolchain do Conan sinh ra (Hỗ trợ CMake >= 3.18)
cmake -B build \
  -DCMAKE_TOOLCHAIN_FILE=build/build/Release/generators/conan_toolchain.cmake \
  -DCMAKE_BUILD_TYPE=Release

# 4. Biên dịch chương trình với giới hạn 2 luồng (-j2) để an toàn bộ nhớ
cmake --build build -j2

# 5. Kiểm tra file thực thi đã sinh ra
ls -lh build/bin/pi_capture_agent_cpp
```

---

## 2. Hướng Dẫn Vận Hành Cả 2 Phương Thức: Wi-Fi & Cáp Ethernet (Laptop Hub Type-C / Jetson)

Phiên bản C++ giữ nguyên hoàn toàn 6 chế độ CLI và 2 phương thức mạng như bản Python để kỹ sư thuận tiện kiểm thử:

### 2.1. Kiểm Tra Nhanh Phần Cứng & Cảm Biến Tại Chỗ (`diag`, `snapshot`, `test-imu`, `test-perf`)
```bash
# 1. Chẩn đoán tổng thể I2C MPU6050 + Media-ctl + V4L2 OV5640
./build/bin/pi_capture_agent_cpp --mode diag

# 2. Chụp 1 bức ảnh 1280x720 kiểm tra độ nét
./build/bin/pi_capture_agent_cpp --mode snapshot --output ./test_720p.jpg

# 3. Kiểm tra góc nghiêng Pitch/Roll 50Hz từ IMU MPU6050
./build/bin/pi_capture_agent_cpp --mode test-imu

# 4. Đo đạc benchmark hiệu năng 100 khung hình
./build/bin/pi_capture_agent_cpp --mode test-perf --frames 100
```

### 2.2. Phương Thức 1: Sử Dụng Mạng Wi-Fi Để Test Nhanh Với Laptop (`preview` & `stream`)
1. **Xem trực tiếp trên trình duyệt Laptop qua Wi-Fi (`--mode preview`):**
   - Trên Pi 3:
     ```bash
     ./build/bin/pi_capture_agent_cpp --mode preview --preview-port 8080
     ```
   - Trên Laptop (cùng mạng Wi-Fi): Mở trình duyệt truy cập `http://<IP_WIFI_PI3>:8080/preview` để quan sát trực tiếp video MJPEG + góc nghiêng IMU và căn chỉnh tiêu cự ống kính.
2. **Truyền luồng nhị phân qua Wi-Fi về Laptop (`--mode stream`):**
   - Trên Laptop: Chạy `uv run python scripts/mock_ingest_server.py --host 0.0.0.0 --port 9876` (hoặc chạy FastAPI Backend `uv run uvicorn app.main:app --host 0.0.0.0 --port 8000`).
   - Trên Pi 3:
     ```bash
     ./build/bin/pi_capture_agent_cpp --mode stream --host <IP_WIFI_LAPTOP> --port 9876
     ```

### 2.3. Phương Thức 2: Sử Dụng Cáp Ethernet Qua Hub Chuyển Đổi Type-C (Với Laptop) Hoặc Cắm Trực Tiếp Vào Jetson AGX Xavier
1. **Khi test với Laptop qua dây mạng Ethernet + Hub Type-C (Không cần gán IP tĩnh):**
   - Cắm cáp mạng Ethernet nối từ cổng RJ45 của Pi 3 vào Hub chuyển đổi Type-C trên Laptop.
   - Trên Laptop, chạy `ipconfig` (Windows) hoặc `ip a` (Linux) để xem địa chỉ IPv4 của card mạng Ethernet thuộc Hub Type-C (ví dụ địa chỉ tự cấu hình APIPA `169.254.x.x` hoặc `192.168.x.x`).
   - Khởi động bộ nhận trên Laptop (`mock_ingest_server.py` hoặc FastAPI Backend trên cổng `9876`).
   - Trên Pi 3 (vẫn điều khiển qua SSH Wi-Fi), chạy lệnh truyền luồng qua đường dây cáp Ethernet:
     ```bash
     ./build/bin/pi_capture_agent_cpp --mode stream --host <IP_ETHERNET_HUB_LAPTOP> --port 9876
     ```
2. **Khi tích hợp thực tế với Jetson AGX Xavier qua cổng Ethernet:**
   - Cắm cáp mạng Ethernet giữa Pi 3 và Switch/cổng Ethernet của Jetson AGX Xavier (`192.168.1.20`):
     ```bash
     ./build/bin/pi_capture_agent_cpp --mode stream --host 192.168.1.20 --port 9876
     ```
