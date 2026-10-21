/**
 * @file socket_streamer.h
 * @brief TCP client streamer with auto-reconnect and exponential backoff.
 *
 * Replaces: pi_capture_agent/streamer.py  (SocketStreamer)
 *
 * Behaviour is identical to the Python version:
 *  - TCP_NODELAY + SO_KEEPALIVE
 *  - Exponential backoff on connection failure (capped at max_backoff)
 *  - Reset backoff on successful connect
 *  - MSG_NOSIGNAL to avoid SIGPIPE on broken connections
 */

#pragma once

#include <cstddef>
#include <cstdint>
#include <string>

class SocketStreamer {
public:
    SocketStreamer(const std::string& host, int port,
                  double retry_delay = 2.0, double max_backoff = 15.0,
                  double connect_timeout = 3.0, double send_timeout = 5.0);
    ~SocketStreamer();

    SocketStreamer(const SocketStreamer&) = delete;
    SocketStreamer& operator=(const SocketStreamer&) = delete;

    /** Attempts to connect with configured timeout. Returns true on success. */
    bool connect();

    /**
     * Sends a complete packet (header + payload) over TCP.
     * Auto-reconnects if disconnected and backoff period has elapsed.
     * @return true if the entire packet was sent successfully.
     */
    bool send_packet(const uint8_t* data, size_t len);

    /** Gracefully closes the socket. */
    void close();

    bool is_connected() const { return connected_; }

private:
    bool sendall(const uint8_t* data, size_t len);

    std::string host_;
    int port_;
    double retry_delay_;
    double max_backoff_;
    double connect_timeout_;
    double send_timeout_;

    int sockfd_ = -1;
    bool connected_ = false;
    double current_backoff_;
    double last_connect_time_ = 0.0;
};
