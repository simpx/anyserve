#include "worker_client.hpp"
#include "grpc_predict_v2.pb.h"

#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>
#include <arpa/inet.h>

#include <iostream>
#include <cstring>

namespace anyserve {

// ============================================================================
// Connection Implementation
// ============================================================================

WorkerClient::Connection::Connection(const std::string& path)
    : socket_path(path) {

    // 创建 Unix Socket
    fd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (fd < 0) {
        std::cerr << "[WorkerClient] Failed to create socket: " << strerror(errno) << std::endl;
        return;
    }

    // 连接到 Worker
    struct sockaddr_un addr;
    std::memset(&addr, 0, sizeof(addr));
    addr.sun_family = AF_UNIX;
    std::strncpy(addr.sun_path, path.c_str(), sizeof(addr.sun_path) - 1);

    if (connect(fd, (struct sockaddr*)&addr, sizeof(addr)) < 0) {
        std::cerr << "[WorkerClient] Failed to connect to " << path
                  << ": " << strerror(errno) << std::endl;
        ::close(fd);
        fd = -1;
        return;
    }
}

WorkerClient::Connection::~Connection() {
    close();
}

WorkerClient::Connection::Connection(Connection&& other) noexcept
    : fd(other.fd), socket_path(std::move(other.socket_path)) {
    other.fd = -1;
}

WorkerClient::Connection& WorkerClient::Connection::operator=(Connection&& other) noexcept {
    if (this != &other) {
        close();
        fd = other.fd;
        socket_path = std::move(other.socket_path);
        other.fd = -1;
    }
    return *this;
}

void WorkerClient::Connection::close() {
    if (fd >= 0) {
        ::close(fd);
        fd = -1;
    }
}

// ============================================================================
// ConnectionPool Implementation
// ============================================================================

std::unique_ptr<WorkerClient::Connection> WorkerClient::ConnectionPool::acquire(
    const std::string& socket_path) {

    // 尝试从池中获取
    if (!available.empty()) {
        auto conn = std::move(available.back());
        available.pop_back();
        in_use++;
        return conn;
    }

    // 创建新连接
    if (in_use < max_connections) {
        auto conn = std::make_unique<Connection>(socket_path);
        if (conn->is_valid()) {
            in_use++;
            return conn;
        }
    }

    return nullptr;
}

void WorkerClient::ConnectionPool::release(std::unique_ptr<Connection> conn) {
    // 不重用连接 - Worker 在每个请求后关闭连接
    // Unix Domain Socket 连接是单次使用的
    if (in_use > 0) {
        in_use--;
    }
    // 让 conn 自动析构，关闭连接
}

// ============================================================================
// WorkerClient Implementation
// ============================================================================

WorkerClient::WorkerClient() = default;

WorkerClient::~WorkerClient() = default;

bool WorkerClient::forward_request(
    const std::string& worker_address,
    const inference::ModelInferRequest& request,
    inference::ModelInferResponse& response) {

    total_requests_++;

    // 1. 提取 socket 路径
    std::string socket_path = extract_socket_path(worker_address);

    // 2. 序列化请求
    std::string request_data;
    if (!request.SerializeToString(&request_data)) {
        std::cerr << "[WorkerClient] Failed to serialize request" << std::endl;
        failed_requests_++;
        return false;
    }

    // 3. 获取连接
    std::unique_ptr<Connection> conn;
    {
        std::lock_guard<std::mutex> lock(mutex_);
        auto& pool = pools_[socket_path];
        conn = pool.acquire(socket_path);
    }

    if (!conn || !conn->is_valid()) {
        std::cerr << "[WorkerClient] Failed to acquire connection to " << socket_path << std::endl;
        failed_requests_++;
        return false;
    }

    // 4. 发送请求
    if (!send_data(*conn, request_data)) {
        std::cerr << "[WorkerClient] Failed to send request" << std::endl;
        failed_requests_++;
        return false;
    }

    // 5. 接收响应
    std::string response_data;
    if (!recv_data(*conn, response_data)) {
        std::cerr << "[WorkerClient] Failed to receive response" << std::endl;
        failed_requests_++;
        return false;
    }

    // 6. 反序列化响应
    if (!response.ParseFromString(response_data)) {
        std::cerr << "[WorkerClient] Failed to parse response" << std::endl;
        failed_requests_++;
        return false;
    }

    // 7. 释放连接
    {
        std::lock_guard<std::mutex> lock(mutex_);
        auto& pool = pools_[socket_path];
        pool.release(std::move(conn));
    }

    return true;
}

bool WorkerClient::send_data(Connection& conn, const std::string& data) {
    // 发送长度（网络字节序）
    uint32_t length = htonl(static_cast<uint32_t>(data.size()));
    if (send(conn.fd, &length, sizeof(length), 0) != sizeof(length)) {
        return false;
    }

    // 发送数据
    size_t sent = 0;
    while (sent < data.size()) {
        ssize_t n = send(conn.fd, data.data() + sent, data.size() - sent, 0);
        if (n <= 0) {
            return false;
        }
        sent += n;
    }

    return true;
}

bool WorkerClient::recv_data(Connection& conn, std::string& data) {
    // 接收长度
    uint32_t length;
    if (recv(conn.fd, &length, sizeof(length), MSG_WAITALL) != sizeof(length)) {
        return false;
    }
    length = ntohl(length);

    // 接收数据
    data.resize(length);
    size_t received = 0;
    while (received < length) {
        ssize_t n = recv(conn.fd, &data[received], length - received, 0);
        if (n <= 0) {
            return false;
        }
        received += n;
    }

    return true;
}

std::string WorkerClient::extract_socket_path(const std::string& worker_address) {
    // 去掉 "unix://" 前缀
    if (worker_address.find("unix://") == 0) {
        return worker_address.substr(7);
    }
    return worker_address;
}

} // namespace anyserve
