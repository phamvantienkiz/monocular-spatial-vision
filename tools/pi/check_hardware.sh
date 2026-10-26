#!/usr/bin/env bash
# ==============================================================================
# Raspberry Pi 3 Hardware & Sensor Exposure Verification Script
# Checks Camera (Pcam 5C / OV5640) + Subdev Exposure/Gain and IMU (MPU-6050)
# ==============================================================================

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}================================================================${NC}"
echo -e "${BLUE}       RASPBERRY PI 3 SENSOR HARDWARE VERIFICATION SCRIPT       ${NC}"
echo -e "${BLUE}================================================================${NC}"

# 1. Check I2C Interface & MPU6050
echo -e "\n${YELLOW}[1/5] Checking I2C Bus & MPU6050 (Address 0x68)...${NC}"
if [ -e /dev/i2c-1 ]; then
    echo -e "  [${GREEN}OK${NC}] /dev/i2c-1 interface detected."
    if command -v i2cdetect &> /dev/null; then
        echo "  Running i2cdetect -y 1:"
        i2cdetect -y 1
        if i2cdetect -y 1 | grep -E "68|69" > /dev/null; then
            echo -e "  [${GREEN}PASS${NC}] MPU6050 detected on I2C bus 1!"
        else
            echo -e "  [${RED}FAIL${NC}] No I2C device detected at 0x68 or 0x69."
            echo "         Check wiring: VCC->3.3V(Pin1), GND->Pin6, SDA->GPIO2(Pin3), SCL->GPIO3(Pin5)."
        fi
    else
        echo -e "  [${YELLOW}WARN${NC}] 'i2c-tools' not installed. Install with: sudo apt install -y i2c-tools"
    fi
else
    echo -e "  [${RED}FAIL${NC}] /dev/i2c-1 does not exist!"
    echo "         Enable I2C: sudo raspi-config nonint do_i2c 0"
    echo "         Add 'dtparam=i2c_arm=on' to /boot/firmware/config.txt and reboot."
fi

# 2. Check CSI Camera & OV5640 Kernel Driver
echo -e "\n${YELLOW}[2/5] Checking Pcam 5C (OV5640) Driver & V4L2 Nodes...${NC}"
if ls /dev/video* 1> /dev/null 2>&1; then
    echo -e "  [${GREEN}OK${NC}] V4L2 video nodes found:"
    ls -l /dev/video* /dev/v4l-subdev* 2>/dev/null || true
    if command -v v4l2-ctl &> /dev/null; then
        echo "  V4L2 Device list:"
        v4l2-ctl --list-devices
        echo "  Available formats on /dev/video0:"
        v4l2-ctl -d /dev/video0 --list-formats-ext 2>/dev/null || true
    fi
else
    echo -e "  [${RED}FAIL${NC}] No /dev/video* devices found!"
    echo "         Ensure ribbon cable is seated properly in MIPI CSI port."
    echo "         Add 'dtoverlay=ov5640' to /boot/firmware/config.txt and reboot."
fi

# 3. Check OV5640 Subdevice Exposure & Gain (15fps vs 30fps Diagnostics)
echo -e "\n${YELLOW}[3/5] Checking OV5640 Subdev Exposure & Gain (/dev/v4l-subdev0)...${NC}"
if [ -e /dev/v4l-subdev0 ] && command -v v4l2-ctl &> /dev/null; then
    v4l2-ctl -d /dev/v4l-subdev0 -C exposure,gain,analogue_gain 2>/dev/null || \
    v4l2-ctl -d /dev/v4l-subdev0 -L 2>/dev/null | grep -E "exposure|gain|flip|power_line" || true
else
    echo "  (/dev/v4l-subdev0 not present or v4l2-ctl missing)"
fi

# 4. Check kernel dmesg for OV5640 & Unicam
echo -e "\n${YELLOW}[4/5] Checking kernel logs (dmesg | grep -iE 'ov5640|unicam')...${NC}"
dmesg | grep -iE "ov5640|unicam" | tail -n 15 || echo "  (No ov5640/unicam messages in dmesg)"

# 5. Check User Permissions
echo -e "\n${YELLOW}[5/5] Checking user group permissions (i2c, video)...${NC}"
USER_GROUPS=$(groups)
if echo "$USER_GROUPS" | grep -q "i2c" && echo "$USER_GROUPS" | grep -q "video"; then
    echo -e "  [${GREEN}PASS${NC}] User belongs to 'i2c' and 'video' groups."
else
    echo -e "  [${YELLOW}WARN${NC}] Current user may need permission."
    echo "         Run: sudo usermod -aG video,i2c \$USER"
fi

echo -e "\n${BLUE}================================================================${NC}"
echo -e "Next steps on Raspberry Pi 3 (C++ Native Pipeline):"
echo "  1. Build C++ Native Service:"
echo "     cd services/pi_capture_native && mkdir -p build && cd build"
echo "     cmake .. -DCMAKE_BUILD_TYPE=Release && make -j2"
echo "  2. Run Hardware & Exposure/Gain Diagnostic:"
echo "     ./pi_capture_native --mode diag --width 640 --height 480 --rotate-180"
echo "  3. Start HTTP Preview Server (view at http://<PI_IP>:8080/ in laptop browser):"
echo "     ./pi_capture_native --mode preview --width 640 --height 480 --rotate-180"
echo "  4. Start 30 FPS Locked Preview (prevent indoor 15fps drop without purple tint):"
echo "     ./pi_capture_native --mode preview --width 640 --height 480 --rotate-180 --lock-30fps --exposure 350 --gain 48"
echo "  5. Stream to Laptop Ingest Server:"
echo "     ./pi_capture_native --mode stream --host <LAPTOP_IP> --port 9876 --rotate-180"
echo -e "${BLUE}================================================================${NC}"
