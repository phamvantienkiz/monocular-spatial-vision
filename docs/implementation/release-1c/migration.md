# Migration & Setup Guide — Release 1c Pure C/C++ Native

> **Layer:** Implementation Layer (`docs/implementation/release-1c/migration.md`)  
> **Release:** Release 1c (C/C++ Native Edge Capture & Perception Pipeline)  
> **Status:** Approved Baseline  

---

## 1. Thiết Lập Môi Trường Cô Lập Tuyệt Đối (Zero System Pollution)

Tuân thủ nghiêm ngặt quy định tại [AGENTS.md](file:///E:/UIT/monocular-spatial-vision/AGENTS.md), không cài đặt bất kỳ thư viện C++ nào vào môi trường toàn cục của hệ điều hành (`/usr/local/`, `/usr/lib/`). Toàn bộ quy trình cài đặt và biên dịch được đóng gói khép kín trong không gian làm việc của repository.

### 1.1. Bước 1: Mở Rộng Bộ Nhớ Swap Trên Raspberry Pi 3 (Bắt Buộc)

Do Pi 3 chỉ có đúng $1\text{GB}$ RAM vật lý, việc biên dịch mã nguồn C++ và nạp các mẫu template phức tạp rất dễ gây cạn kiệt RAM làm Linux kernel kích hoạt OOM Killer gây treo máy. Cần thiết lập Swap tối thiểu $2048\text{MB}$:

```bash
# 1. Chỉnh sửa cấu hình dphys-swapfile
sudo nano /etc/dphys-swapfile

# 2. Thay đổi giá trị thành:
# CONF_SWAPSIZE=2048

# 3. Khởi động lại dịch vụ swap
sudo systemctl restart dphys-swapfile

# 4. Kiểm tra lại dung lượng swap sẵn sàng
free -h
# Swap: total 2.0Gi
```

---

### 1.2. Bước 2: Thiết Lập Quyền Truy Cập Phần Cứng Không Cần Sudo

Đảm bảo tài khoản người dùng (`pi` hoặc `r3b`) có quyền truy cập trực tiếp các node thiết bị V4L2 và I2C:

```bash
# Thêm user vào nhóm video và i2c
sudo usermod -aG video,i2c $USER

# Kích hoạt I2C nếu chưa bật
sudo raspi-config nonint do_i2c 0

# Đăng xuất và đăng nhập lại để quyền có hiệu lực
exit
```

---

### 1.3. Bước 3: Khởi Tạo Môi Trường Ảo Bằng `uv` & Cài Đặt Conan 2.0

Chúng ta tận dụng chính môi trường ảo `.venv` của Python (được tạo bởi `uv`) để làm vỏ bọc quản lý công cụ `conan` cho C++:

```bash
# Di chuyển vào thư mục gốc của dự án
cd ~/workspaces/monocular-spatial-vision

# Khởi tạo môi trường ảo biệt lập bằng uv
uv venv

# Cài đặt Conan 2.0 trực tiếp vào .venv (hoàn toàn không đụng tới Python global)
uv pip install conan

# Kích hoạt môi trường
source .venv/bin/activate

# Kiểm tra phiên bản conan
uv run conan --version
# Conan version 2.x.x
```

---

### 1.4. Bước 4: Cấu Hình Cache Cục Bộ `CONAN_HOME` & Profile Phần Cứng

Conan mặc định sẽ lưu cache tại `~/.conan2` (thư mục User). Để cô lập $100\%$ trong workspace của dự án:

```bash
# Đặt biến môi trường CONAN_HOME trỏ vào thư mục .conan ngay trong repo
export CONAN_HOME="$(pwd)/.conan"

# Tự động nhận diện cấu hình trình biên dịch của Raspberry Pi 3
uv run conan profile detect --force
```

Tệp profile sinh ra tại `.conan/profiles/default` sẽ tự động xác định kiến trúc ARM (`armv7hf` cho hệ điều hành 32-bit hoặc `armv8`/`aarch64` cho hệ điều hành 64-bit) và phiên bản `gcc`/`g++` sẵn có trên máy.

---

### 1.5. Bước 5: Cài Đặt Phụ Thuộc C++ & Biên Dịch Dự Án

```bash
# 1. Đặt CONAN_HOME và cài đặt các phụ thuộc từ conanfile.txt
export CONAN_HOME="$(pwd)/.conan"
uv run conan install . --build=missing -s build_type=Release

# 2. Sinh cấu hình CMake sử dụng toolchain do Conan tạo ra
cmake -B build -DCMAKE_TOOLCHAIN_FILE=build/Release/generators/conan_toolchain.cmake -DCMAKE_BUILD_TYPE=Release

# 3. Biên dịch chương trình (RẤT QUAN TRỌNG: Chỉ dùng tối đa -j2 để tránh tràn RAM)
cmake --build build -j2

# 4. Kiểm tra file thực thi đã sinh ra
ls -lh build/bin/pi_capture_agent_cpp
```

---

## 2. Bảng Kiểm Tra Xác Minh Không Ô Nhiễm Hệ Thống (Zero-Pollution Audit)

Trước khi nghiệm thu bất kỳ thay đổi nào, kỹ sư thực hiện lệnh kiểm tra sau để chứng minh tính cô lập tuyệt đối:

```bash
# 1. Kiểm tra các thư mục sinh ra có nằm trọn trong repo không:
ls -d .venv .conan build

# 2. Kiểm tra thư mục hệ thống /usr/local không bị thêm file lạ:
ls -lt /usr/local/bin | head -n 5
ls -lt /usr/local/lib | head -n 5

# 3. Khi muốn dọn dẹp sạch sẽ 100%:
rm -rf .venv .conan build
# -> Máy tính trở về trạng thái nguyên bản sạch sẽ ban đầu!
```

---

## 3. Quy Trình Chạy Thử Nghiệm Nhanh

```bash
# Chạy thử nghiệm chế độ đo hiệu năng 100 frames
./build/bin/pi_capture_agent_cpp --mode test-perf --frames 100

# Chạy thử nghiệm chế độ phát stream sang máy tính Developer (Laptop / Jetson)
./build/bin/pi_capture_agent_cpp --mode stream --host 192.168.1.100 --port 9876
```
