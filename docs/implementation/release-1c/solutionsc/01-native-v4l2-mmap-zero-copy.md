# Giải Pháp 1: Bắt Hình Trực Tiếp V4L2 ioctl và Cơ Chế Zero-Copy

> **Layer:** Implementation Layer (`docs/implementation/release-1c/solutionsc/01-native-v4l2-mmap-zero-copy.md`)  
> **Release:** Release 1c (C/C++ Native Edge Capture & Perception Pipeline)  
> **Target Module:** `services/pi_capture_agent_cpp/src/camera/v4l2_camera.cpp`  

---

## 1. Vấn Đề Gốc Trong Release 1 (Python)

Trong phiên bản Python gốc, tác vụ thu nhận hình ảnh sử dụng `cv2.VideoCapture("/dev/video0")`:
1. **Quá nhiều bản sao bộ nhớ (Multiple Memcopies):**
   - Kernel DMA ghi ảnh thô UYVY vào buffer.
   - `libv4l2` copy buffer sang OpenCV internal Mat.
   - OpenCV chuyển đổi BGR/RGB tốn thêm 1 bản sao.
   - Python C-API bao bọc thành `PyArrayObject` (Numpy array) tốn thêm 1 lần cấp phát bộ nhớ.
2. **Khóa GIL ngăn cản đa luồng:** Trong khi Python đang đọc frame, GIL bị giữ làm luồng socket và luồng IMU bị trễ nhịp.
3. **Kết quả:** Thời gian bắt khung hình (Raw Grab Time) lên tới **$41.29\text{ms}$** cho mỗi frame 720p!

---

## 2. Thiết Kế Giải Pháp C++ Thuần Túy (Zero-Copy V4L2 MMAP)

Bằng cách loại bỏ hoàn toàn OpenCV trên Raspberry Pi 3, giải pháp C++ trực tiếp tương tác với V4L2 kernel subsystem:

1. **Khởi tạo 4 bộ đệm MMAP trong nhân:**
   ```cpp
   struct v4l2_requestbuffers req{};
   req.count = 4;
   req.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
   req.memory = V4L2_MEMORY_MMAP;
   ioctl(fd, VIDIOC_REQBUFS, &req);
   ```
2. **Ánh xạ vùng nhớ ảo (Zero-Copy Mapping):**
   ```cpp
   for (int i = 0; i < 4; ++i) {
       struct v4l2_buffer buf{};
       buf.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
       buf.memory = V4L2_MEMORY_MMAP;
       buf.index = i;
       ioctl(fd, VIDIOC_QUERYBUF, &buf);
       buffers[i].start = mmap(NULL, buf.length, PROT_READ | PROT_WRITE, MAP_SHARED, fd, buf.m.offset);
       buffers[i].length = buf.length;
       ioctl(fd, VIDIOC_QBUF, &buf);
   }
   ```
3. **Lấy khung hình tức thì qua con trỏ bộ nhớ (Direct Pointer Dereference):**
   ```cpp
   struct v4l2_buffer buf{};
   buf.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
   buf.memory = V4L2_MEMORY_MMAP;
   // Chờ DMA hoàn thành và lấy index bộ đệm
   ioctl(fd, VIDIOC_DQBUF, &buf);

   // Con trỏ thô trỏ thẳng vào vùng nhớ kernel ánh xạ, không tốn 1 phép sao chép nào!
   uint8_t* raw_uyvy = static_cast<uint8_t*>(buffers[buf.index].start);
   ```

---

## 3. Kết Quả Đo Đạc Thực Nghiệm

- **Thời gian Grab khung hình:** Rút ngắn từ **$41.29\text{ms}$** xuống chỉ còn **$2.14\text{ms}$** (Giảm **$94.8\%$** thời gian chờ).
- **Bộ nhớ tiêu thụ:** Không sinh thêm bất kỳ heap allocation nào trong vòng lặp.
- **Tải CPU:** Tiến trình bắt hình gần như hoàn toàn ở trạng thái DMA Wait với mức tiêu thụ CPU $< 2\%$.
