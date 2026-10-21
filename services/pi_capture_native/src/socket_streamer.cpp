/**
 * @file socket_streamer.cpp
 * @brief TCP client with auto-reconnect — direct POSIX sockets.
 *
 * Replaces: pi_capture_agent/streamer.py  (SocketStreamer)
 *
 * Behaviour-identical to Python version:
 *  - connect() with timeout via select()
 *  - TCP_NODELAY + SO_KEEPALIVE
 *  - Exponential backoff on failures (capped at max_backoff_)
 *  - MSG_NOSIGNAL to avoid SIGPIPE crash
 */

#include "socket_streamer.h"
#include "log.h"

#include <cerrno>
#include <cstring>

#include <arpa/inet.h>
#include <fcntl.h>
#include <netinet/tcp.h>
#include <sys/select.h>
#include <sys/socket.h>
#include <unistd.h>

/* ── constructor / destructor ──────────────────────────────────────── */

SocketStreamer::SocketStreamer(const std::string& host, int port,
                              double retry_delay, double max_backoff,
                              double connect_timeout, double send_timeout)
    : host_(host), port_(port),
      retry_delay_(retry_delay), max_backoff_(max_backoff),
      connect_timeout_(connect_timeout), send_timeout_(send_timeout),
      current_backoff_(retry_delay) {}

SocketStreamer::~SocketStreamer() { close(); }

/* ── connect ───────────────────────────────────────────────────────── */

bool SocketStreamer::connect() {
    close();
    last_connect_time_ = time_now_sec();
    LOG_INFO("Attempting connection to ingest server at %s:%d...", host_.c_str(), port_);

    sockfd_ = socket(AF_INET, SOCK_STREAM, 0);
    if (sockfd_ < 0) {
        LOG_WARN("socket() failed: %s", strerror(errno));
        return false;
    }

    /* Non-blocking connect with timeout */
    int flags = fcntl(sockfd_, F_GETFL, 0);
    fcntl(sockfd_, F_SETFL, flags | O_NONBLOCK);

    struct sockaddr_in addr{};
    addr.sin_family = AF_INET;
    addr.sin_port   = htons(static_cast<uint16_t>(port_));
    if (inet_pton(AF_INET, host_.c_str(), &addr.sin_addr) <= 0) {
        LOG_ERROR("Invalid host address: %s", host_.c_str());
        close();
        return false;
    }

    int ret = ::connect(sockfd_, reinterpret_cast<struct sockaddr*>(&addr), sizeof(addr));
    if (ret < 0 && errno != EINPROGRESS) {
        LOG_WARN("connect() failed: %s. Retrying in %.1fs...",
                 strerror(errno), current_backoff_);
        close();
        return false;
    }

    /* Wait for connect to complete */
    fd_set wfds;
    FD_ZERO(&wfds);
    FD_SET(sockfd_, &wfds);
    long sec = static_cast<long>(connect_timeout_);
    long usec = static_cast<long>((connect_timeout_ - sec) * 1e6);
    struct timeval tv = {sec, usec};

    ret = select(sockfd_ + 1, nullptr, &wfds, nullptr, &tv);
    if (ret <= 0) {
        LOG_WARN("Connection timed out to %s:%d. Retrying in %.1fs...",
                 host_.c_str(), port_, current_backoff_);
        close();
        return false;
    }

    /* Check socket error */
    int so_err = 0;
    socklen_t so_len = sizeof(so_err);
    getsockopt(sockfd_, SOL_SOCKET, SO_ERROR, &so_err, &so_len);
    if (so_err != 0) {
        LOG_WARN("Connection failed: %s. Retrying in %.1fs...",
                 strerror(so_err), current_backoff_);
        close();
        return false;
    }

    /* Restore blocking mode */
    fcntl(sockfd_, F_SETFL, flags);

    /* Low-latency socket options (same as Python: TCP_NODELAY + SO_KEEPALIVE) */
    int one = 1;
    setsockopt(sockfd_, IPPROTO_TCP, TCP_NODELAY, &one, sizeof(one));
    setsockopt(sockfd_, SOL_SOCKET, SO_KEEPALIVE, &one, sizeof(one));

    /* Send timeout */
    long s_sec = static_cast<long>(send_timeout_);
    long s_usec = static_cast<long>((send_timeout_ - s_sec) * 1e6);
    struct timeval stv = {s_sec, s_usec};
    setsockopt(sockfd_, SOL_SOCKET, SO_SNDTIMEO, &stv, sizeof(stv));

    connected_ = true;
    current_backoff_ = retry_delay_;  /* Reset backoff on success */
    LOG_INFO("Connected to ingest server at %s:%d.", host_.c_str(), port_);
    return true;
}

/* ── sendall ───────────────────────────────────────────────────────── */

bool SocketStreamer::sendall(const uint8_t* data, size_t len) {
    size_t sent = 0;
    while (sent < len) {
        ssize_t n = ::send(sockfd_, data + sent, len - sent, MSG_NOSIGNAL);
        if (n <= 0) return false;
        sent += static_cast<size_t>(n);
    }
    return true;
}

/* ── send_packet ───────────────────────────────────────────────────── */

bool SocketStreamer::send_packet(const uint8_t* data, size_t len) {
    double now = time_now_sec();

    if (!connected_) {
        if (now - last_connect_time_ >= current_backoff_) {
            if (!connect()) {
                current_backoff_ = std::min(current_backoff_ * 1.5, max_backoff_);
                return false;
            }
        } else {
            return false;  /* Backoff period not expired */
        }
    }

    if (sockfd_ < 0) return false;

    if (!sendall(data, len)) {
        LOG_WARN("Socket error during transmission. Closing connection.");
        close();
        last_connect_time_ = now;
        current_backoff_ = std::min(current_backoff_ * 1.5, max_backoff_);
        return false;
    }
    return true;
}

/* ── close ─────────────────────────────────────────────────────────── */

void SocketStreamer::close() {
    if (sockfd_ >= 0) {
        shutdown(sockfd_, SHUT_RDWR);
        ::close(sockfd_);
        sockfd_ = -1;
    }
    connected_ = false;
}
