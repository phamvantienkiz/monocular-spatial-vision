/**
 * @file imu_reader.h
 * @brief MPU6050 6-DOF IMU reader over Linux I2C (/dev/i2c-*).
 *
 * Replaces: pi_capture_agent/imu.py  (IMUReader)
 *
 * Key differences from Python version:
 *  - Direct I2C via Linux i2c-dev (no smbus2 Python dependency)
 *  - Same register map, same complementary filter (alpha=0.98)
 *  - All computations are single-precision float (sufficient for IMU)
 */

#pragma once

#include <cstdint>

struct Attitude {
    float pitch_deg = 0.0f;
    float roll_deg  = 0.0f;
    float ax = 0.0f, ay = 0.0f, az = 0.0f;  // acceleration in g
};

class ImuReader {
public:
    /**
     * @param bus_id      I2C bus number (1 for /dev/i2c-1 on Raspberry Pi).
     * @param address     MPU6050 slave address (0x68 if AD0=GND).
     * @param alpha       Complementary filter weight (0.0–1.0, default 0.98).
     * @param use_filter  Enable gyro-integrated complementary filter.
     */
    ImuReader(int bus_id = 1, int address = 0x68,
              float alpha = 0.98f, bool use_filter = true);
    ~ImuReader();

    ImuReader(const ImuReader&) = delete;
    ImuReader& operator=(const ImuReader&) = delete;

    /** Wakes MPU6050, configures sample rate / DLPF / scale ranges. */
    bool initialize();

    /** Closes the I2C file descriptor. */
    void close();

    bool is_initialized() const { return initialized_; }

    /**
     * Reads accelerometer + gyroscope, computes pitch/roll with complementary filter.
     * Safe to call at sensor rate (~125 Hz) or per-frame (~30 Hz).
     */
    Attitude read_attitude();

private:
    int16_t read_word(uint8_t reg);
    bool    write_byte(uint8_t reg, uint8_t val);

    int bus_id_;
    int address_;
    float alpha_;
    bool use_filter_;

    int  fd_ = -1;
    bool initialized_ = false;

    // Complementary filter state
    float  last_pitch_ = 0.0f;
    float  last_roll_  = 0.0f;
    double last_time_  = 0.0;
    bool   first_reading_ = true;
};
