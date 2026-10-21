/**
 * @file imu_reader.cpp
 * @brief MPU6050 I2C driver — direct Linux i2c-dev access.
 *
 * Replaces: pi_capture_agent/imu.py  (IMUReader)
 *
 * Register map and complementary filter logic are identical to the Python version.
 * Uses /dev/i2c-* with ioctl(I2C_SLAVE) instead of Python smbus2.
 */

#include "imu_reader.h"
#include "log.h"

#include <cerrno>
#include <cmath>
#include <cstring>

#include <fcntl.h>
#include <linux/i2c-dev.h>
#include <sys/ioctl.h>
#include <unistd.h>

/* ── MPU6050 Register Map (same as imu.py) ─────────────────────────── */

static constexpr uint8_t REG_SMPLRT_DIV   = 0x19;
static constexpr uint8_t REG_CONFIG       = 0x1A;
static constexpr uint8_t REG_GYRO_CONFIG  = 0x1B;
static constexpr uint8_t REG_ACCEL_CONFIG = 0x1C;
static constexpr uint8_t REG_ACCEL_XOUT_H = 0x3B;
static constexpr uint8_t REG_PWR_MGMT_1   = 0x6B;
static constexpr uint8_t REG_WHO_AM_I     = 0x75;

/* Scaling factors for ±2g and ±250 deg/s defaults */
static constexpr float ACCEL_SCALE_2G = 16384.0f;
static constexpr float GYRO_SCALE_250 = 131.0f;

/* ── constructor / destructor ──────────────────────────────────────── */

ImuReader::ImuReader(int bus_id, int address, float alpha, bool use_filter)
    : bus_id_(bus_id), address_(address), alpha_(alpha), use_filter_(use_filter) {}

ImuReader::~ImuReader() { close(); }

/* ── low-level I2C ─────────────────────────────────────────────────── */

bool ImuReader::write_byte(uint8_t reg, uint8_t val) {
    uint8_t buf[2] = {reg, val};
    return ::write(fd_, buf, 2) == 2;
}

int16_t ImuReader::read_word(uint8_t reg) {
    if (::write(fd_, &reg, 1) != 1) return 0;
    uint8_t buf[2] = {0, 0};
    if (::read(fd_, buf, 2) != 2) return 0;
    return static_cast<int16_t>((buf[0] << 8) | buf[1]); /* big-endian */
}

/* ── initialize ────────────────────────────────────────────────────── */

bool ImuReader::initialize() {
    char dev_path[32];
    snprintf(dev_path, sizeof(dev_path), "/dev/i2c-%d", bus_id_);

    fd_ = ::open(dev_path, O_RDWR);
    if (fd_ < 0) {
        LOG_ERROR("Cannot open %s: %s", dev_path, strerror(errno));
        return false;
    }

    if (ioctl(fd_, I2C_SLAVE, address_) < 0) {
        LOG_ERROR("I2C_SLAVE 0x%02X failed: %s", address_, strerror(errno));
        close();
        return false;
    }

    /* Wake up MPU6050: clock source = PLL with X gyro (0x01) */
    if (!write_byte(REG_PWR_MGMT_1, 0x01)) {
        LOG_ERROR("Failed to wake MPU6050");
        close();
        return false;
    }
    usleep(10000); /* 10ms settle */

    /* Sample rate divider: 1kHz / (1 + 7) = 125 Hz */
    write_byte(REG_SMPLRT_DIV, 0x07);

    /* DLPF config 3: Accel BW ~44Hz, Gyro BW ~42Hz */
    write_byte(REG_CONFIG, 0x03);

    /* Gyro ±250 deg/s */
    write_byte(REG_GYRO_CONFIG, 0x00);

    /* Accelerometer ±2g */
    write_byte(REG_ACCEL_CONFIG, 0x00);

    /* Verify WHO_AM_I */
    int16_t who = read_word(REG_WHO_AM_I);
    /* read_word reads 2 bytes but WHO_AM_I is 1 byte (high byte) */
    uint8_t who_id = static_cast<uint8_t>(who >> 8);
    LOG_INFO("MPU6050 initialised: bus=%d addr=0x%02X WHO_AM_I=0x%02X",
             bus_id_, address_, who_id);

    initialized_ = true;
    return true;
}

/* ── read_attitude ─────────────────────────────────────────────────
 * Burst-reads 14 bytes: Accel(6) + Temp(2) + Gyro(6)
 * Computes pitch/roll with complementary filter — identical to imu.py
 * ──────────────────────────────────────────────────────────────────── */

Attitude ImuReader::read_attitude() {
    Attitude att;

    if (!initialized_ || fd_ < 0) return att;

    /* Burst read 14 bytes starting from ACCEL_XOUT_H */
    uint8_t reg = REG_ACCEL_XOUT_H;
    if (::write(fd_, &reg, 1) != 1) return att;

    uint8_t raw[14];
    if (::read(fd_, raw, 14) != 14) return att;

    /* Parse big-endian 16-bit signed values */
    auto parse = [&](int offset) -> int16_t {
        return static_cast<int16_t>((raw[offset] << 8) | raw[offset + 1]);
    };

    float ax = parse(0)  / ACCEL_SCALE_2G;
    float ay = parse(2)  / ACCEL_SCALE_2G;
    float az = parse(4)  / ACCEL_SCALE_2G;
    /* temp at offset 6-7 (skipped) */
    float gx = parse(8)  / GYRO_SCALE_250;  /* deg/s */
    float gy = parse(10) / GYRO_SCALE_250;
    /* gz at offset 12-13 (not needed for pitch/roll) */

    att.ax = ax;
    att.ay = ay;
    att.az = az;

    /* Accelerometer-only static angles (same formulas as imu.py) */
    float norm_yz = sqrtf(ay * ay + az * az);
    if (norm_yz < 1e-6f) norm_yz = 1e-6f;
    float pitch_acc = atan2f(-ax, norm_yz) * (180.0f / static_cast<float>(M_PI));
    float az_safe = (fabsf(az) > 1e-6f) ? az : 1e-6f;
    float roll_acc  = atan2f(ay, az_safe) * (180.0f / static_cast<float>(M_PI));

    double now = time_now_sec();

    if (!use_filter_ || first_reading_) {
        att.pitch_deg = pitch_acc;
        att.roll_deg  = roll_acc;
        first_reading_ = false;
    } else {
        double dt = now - last_time_;
        if (dt > 0.0005 && dt < 0.5) {
            /* Complementary filter: high-pass gyro + low-pass accel */
            float pitch_gyro = last_pitch_ + gy * static_cast<float>(dt);
            float roll_gyro  = last_roll_  + gx * static_cast<float>(dt);

            att.pitch_deg = alpha_ * pitch_gyro + (1.0f - alpha_) * pitch_acc;
            att.roll_deg  = alpha_ * roll_gyro  + (1.0f - alpha_) * roll_acc;
        } else {
            /* dt out of bounds — fallback to accel only */
            att.pitch_deg = pitch_acc;
            att.roll_deg  = roll_acc;
        }
    }

    last_pitch_ = att.pitch_deg;
    last_roll_  = att.roll_deg;
    last_time_  = now;

    return att;
}

/* ── close ─────────────────────────────────────────────────────────── */

void ImuReader::close() {
    if (fd_ >= 0) {
        ::close(fd_);
        fd_ = -1;
    }
    initialized_ = false;
}
