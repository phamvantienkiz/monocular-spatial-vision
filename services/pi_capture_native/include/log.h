/**
 * @file log.h
 * @brief Minimal logging macros and time utilities for pi_capture_native.
 */

#pragma once

#include <cstdint>
#include <cstdio>
#include <ctime>

#define LOG_INFO(fmt, ...)  fprintf(stderr, "[INFO]  " fmt "\n", ##__VA_ARGS__)
#define LOG_WARN(fmt, ...)  fprintf(stderr, "[WARN]  " fmt "\n", ##__VA_ARGS__)
#define LOG_ERROR(fmt, ...) fprintf(stderr, "[ERROR] " fmt "\n", ##__VA_ARGS__)

/** Returns monotonic seconds (for elapsed/backoff/benchmark timing). */
inline double time_now_sec() {
    struct timespec ts{};
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return static_cast<double>(ts.tv_sec) + ts.tv_nsec * 1e-9;
}

/** Returns wall-clock nanoseconds (matches Python time.time_ns()). */
inline uint64_t timestamp_ns() {
    struct timespec ts{};
    clock_gettime(CLOCK_REALTIME, &ts);
    return static_cast<uint64_t>(ts.tv_sec) * 1000000000ULL + static_cast<uint64_t>(ts.tv_nsec);
}
