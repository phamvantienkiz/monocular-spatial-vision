/**
 * @file socket_streamer.h
 * @brief TCP client streamer with auto-reconnect, TCP_NODELAY, SO_SNDBUF cap, and exponential backoff.
 *
 * Replaces: pi_capture_agent/streamer.py  (SocketStreamer)
 *
 * Behaviour is identical to the Python version:
 *  - TCP_NODELAY + SO_KEEPALIVE + SO_SNDBUF (prevents Wi-Fi bufferbloat)
 *  - Exponential backoff on connection failure (capped at max_backoff)
 *  - Reset backoff on successful connect
 *  - MSG_NOSIGNAL + atomic sendall() to avoid SIGPIPE and partial framing desync
 */

#pragma once

#include <cstddef>
#include <cstdint>
#include <string>

class SocketStreamer {
public:
    /**
     * @param host             Target IP address (e.g. "192.168.1.20" or Laptop IP).
     * @param port             Target TCP port   (default 9876).
     * @param retry_delay      Initial reconnect wait in seconds (default 2.0).
     * @param max_backoff      Maximum reconnect wait in seconds (default 15.0).
     * @param connect_timeout  TCP connect timeout in seconds   (default 3.0).
     * @param send_timeout     TCP send timeout in seconds      (default 2.0).
     */
    SocketStreamer(const std::string& host, int port,
                   double retry_delay = 2.0, double max_backoff = 15.0,
                   double connect_timeout = 3.0, double send_timeout = 2.0);
    ~SocketStreamer();

    SocketStreamer(const SocketStreamer&) = delete;
    SocketStreamer& operator=(const SocketStreamer&) = delete;

    /** Attempts non-blocking TCP connection with timeout. */
    bool connect();

    /**
     * Sends a complete binary packet (header + JPEG).
     * Automatically reconnects with exponential backoff if disconnected.
     */
    bool send_packet(const uint8_t* data, size_t len);

    /** Closes socket cleanly. */
    void close();

    bool is_connected() const { return connected_; }

private:
    bool sendall(const uint8_t* data, size_t len);

    std::string host_;
    int         port_;
    double      retry_delay_;
    double      max_backoff_;
    double      connect_timeout_;
    double      send_timeout_;

    int    sockfd_            = -1;
    bool   connected_         = false;
    double last_connect_time_ = 0.0;
    double current_backoff_   = 2.0;
};
