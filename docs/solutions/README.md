# Optimization Solutions

Tài liệu giải pháp tối ưu hóa hiệu năng Raspberry Pi 3 Capture Agent được đặt chính thức tại:
👉 [`docs/implementation/release-1/solutions/`](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1/solutions/README.md)

### Danh mục tài liệu:
- [01-hardware-flip-ov5640.md](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1/solutions/01-hardware-flip-ov5640.md): Lật ảnh bằng phần cứng OV5640
- [02-arm-neon-turbojpeg.md](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1/solutions/02-arm-neon-turbojpeg.md): Tăng tốc nén JPEG bằng PyTurboJPEG ARM NEON SIMD
- [03-bcm2835-codec-hardware-m2m.md](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1/solutions/03-bcm2835-codec-hardware-m2m.md): Khai thác VideoCore IV Hardware Codec V4L2 M2M
- [04-comparative-benchmark-and-plan.md](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1/solutions/04-comparative-benchmark-and-plan.md): Bảng đối chuẩn thực nghiệm và kế hoạch triển khai
- [05-sensor-hardware-binning-640.md](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1/solutions/05-sensor-hardware-binning-640.md): Phân tích Crop vs Resize & Hardware 2x2 Binning 640x360
- [06-multithreaded-pipeline-and-videocore-vpu.md](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1/solutions/06-multithreaded-pipeline-and-videocore-vpu.md): Đường ống bất đồng bộ đa luồng & Tích hợp VideoCore IV VPU
