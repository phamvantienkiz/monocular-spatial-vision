# US-C03: Quản Lý Phụ Thuộc Cô Lập Bằng uv + Conan 2.0 & Safe Native Build Harness

> **Layer:** Implementation Layer (`docs/implementation/release-1c/backlogc/storiesc/US-C03.md`)  
> **Release:** Release 1c (C/C++ Native Edge Capture & Perception Pipeline)  
> **Story ID:** US-C03  
> **Status:** Ready for Development  

---

## 1. User Story

**Là một** Kỹ sư DevOps & Kiến Trúc Hệ Thống (DevOps & Systems Architect),  
**Tôi muốn** thiết lập quy trình quản lý thư viện C++ bằng `Conan 2.0` được cài đặt cô lập trong môi trường ảo `.venv` của `uv`, với cache `CONAN_HOME` nằm trọn trong thư mục dự án và harness biên dịch CMake giới hạn tối đa 2 luồng (`-j2`),  
**Để** thỏa mãn $100\%$ nguyên tắc Zero System Pollution tại `AGENTS.md`, đồng thời loại bỏ nguy cơ tràn RAM (OOM) làm đơ cứng Raspberry Pi 3 khi biên dịch mã nguồn C++.

---

## 2. Acceptance Criteria (Given-When-Then)

### Kịch bản 1: Cài đặt Conan trong môi trường ảo cô lập
- **Given:** Máy tính Raspberry Pi 3 hoặc Laptop đã cài đặt `uv`.
- **When:** Kỹ sư chạy lệnh `uv venv` và `uv pip install conan`.
- **Then:**
  1. Thư mục `.venv` được tạo cục bộ trong root workspace.
  2. Binary `conan` nằm trong `.venv/bin/conan`, hoàn toàn không có gói nào được cài vào Python global hệ điều hành (`/usr/local/lib/python*`).

### Kịch bản 2: Cấu hình CONAN_HOME cục bộ trong workspace
- **Given:** Biến môi trường `CONAN_HOME` được export trỏ vào `${PWD}/.conan`.
- **When:** Chạy lệnh `uv run conan install . --build=missing -s build_type=Release`.
- **Then:**
  1. Tất cả recipe, package binary của `libjpeg-turbo`, `nlohmann_json`, `yaml-cpp` được tải và lưu trọn trong thư mục `.conan/p/` của repo.
  2. Thư mục `~/.conan2` của user không bị tạo ra hoặc không bị ghi bất kỳ file nào.

### Kịch bản 3: Sinh CMake Toolchain & Biên dịch an toàn với Swap 2GB
- **Given:** Swap memory trên Pi 3 đã được kích hoạt $\ge 2048\text{MB}$ qua `/etc/dphys-swapfile`.
- **When:** Chạy lệnh cấu hình `cmake -B build -DCMAKE_TOOLCHAIN_FILE=build/Release/generators/conan_toolchain.cmake` và biên dịch bằng `cmake --build build -j2`.
- **Then:**
  1. Trình biên dịch `g++` chỉ chạy tối đa 2 luồng song song, mức chiếm dụng RAM không vượt quá $750\text{MB}$.
  2. Toàn bộ tiến trình biên dịch hoàn tất $100\%$ thành công, sinh ra file thực thi `build/bin/pi_capture_agent_cpp` mà không bị kích hoạt OOM Killer.

### Kịch bản 4: Kiểm toán không để lại rác (Zero-Pollution Audit)
- **Given:** Quá trình build và chạy thử nghiệm đã hoàn tất.
- **When:** Kỹ sư thực hiện xóa 3 thư mục cục bộ `rm -rf .venv .conan build`.
- **Then:** Toàn bộ hệ điều hành trở về trạng thái nguyên bản sạch sẽ ban đầu, không có bất kỳ file rác hay biến môi trường nào bị lưu lại trên máy.

---

## 3. ARCHITECTURE GUARDRAILS FOR CODING AGENT

> ⛔ **BẮT BUỘC TUÂN THỦ:** Trước khi viết hoặc sửa đổi mã nguồn, AI Coding Agent phải đối chiếu các ràng buộc kiến trúc sau:

1. **Tuân Thủ Nghiêm Ngặt Quy Định Cách Ly Môi Trường:**
   - Đối chiếu: [AGENTS.md - Mục 3: Environment Isolation & Script Execution Rules](file:///E:/UIT/monocular-spatial-vision/AGENTS.md).
   - *Ràng buộc:* Nghiêm cấm chạy bare `pip install conan` hoặc `apt install libjpeg-dev` để giải quyết dependency. Mọi phụ thuộc C++ phải khai báo trong `conanfile.txt`.
2. **Quy Tắc Biên Dịch Native Trên Phần Cứng Giới Hạn:**
   - Đối chiếu: [docs/architecture/04-deployment-architecture.md](file:///E:/UIT/monocular-spatial-vision/docs/architecture/04-deployment-architecture.md).
   - *Ràng buộc:* Không bao giờ được phép để lệnh `make` hoặc `cmake --build` chạy không có cờ giới hạn (`-j1` hoặc `-j2`) trên Pi 3.
3. **Cấu Trúc Tệp Khai Báo Phụ Thuộc:**
   - Đối chiếu: [docs/architecture/10-folder-structure.md](file:///E:/UIT/monocular-spatial-vision/docs/architecture/10-folder-structure.md).
   - *Ràng buộc:* File `conanfile.txt` và `CMakeLists.txt` phải đặt ở thư mục dịch vụ C++ `services/pi_capture_agent_cpp/` hoặc root repo tương ứng.
