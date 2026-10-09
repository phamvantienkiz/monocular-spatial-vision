#!/usr/bin/env bash
# ==============================================================================
# Raspberry Pi 3 Hardware Verification Script
# Checks Camera (Pcam 5C / OV5640) and IMU (MPU-6050) connectivity
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
echo -e "\n${YELLOW}[1/4] Checking I2C Bus & MPU6050 (Address 0x68)...${NC}"
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
echo -e "\n${YELLOW}[2/4] Checking Pcam 5C (OV5640) Driver & V4L2 Nodes...${NC}"
if ls /dev/video* 1> /dev/null 2>&1; then
    echo -e "  [${GREEN}OK${NC}] V4L2 video nodes found:"
    ls -l /dev/video*
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

# Check kernel dmesg for OV5640
echo -e "\n${YELLOW}[3/4] Checking kernel logs (dmesg | grep -i ov5640)...${NC}"
dmesg | grep -i ov5640 || echo "  (No ov5640 messages in dmesg)"

# 4. Check User Permissions
echo -e "\n${YELLOW}[4/4] Checking user group permissions (i2c, video)...${NC}"
USER_GROUPS=$(groups)
if echo "$USER_GROUPS" | grep -q "i2c" && echo "$USER_GROUPS" | grep -q "video"; then
    echo -e "  [${GREEN}PASS${NC}] User belongs to 'i2c' and 'video' groups."
else
    echo -e "  [${YELLOW}WARN${NC}] Current user may need permission."
    echo "         Run: sudo usermod -aG video,i2c \$USER"
fi

echo -e "\n${BLUE}================================================================${NC}"
echo -e "Next steps on Raspberry Pi 3:"
echo "  1. Activate virtual environment:"
echo "     cd services/pi_capture_agent && source .venv/bin/activate"
echo "  2. Test IMU readout in real-time:"
echo "     python -m pi_capture_agent.cli --mode test-imu"
echo "  3. Capture single snapshot:"
echo "     python -m pi_capture_agent.cli --mode snapshot --output ./test_frame.jpg"
echo "  4. Start HTTP preview server (view in laptop browser):"
echo "     python -m pi_capture_agent.cli --mode preview --preview-port 8080"
echo -e "${BLUE}================================================================${NC}"
