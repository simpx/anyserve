#pragma once

#include <string>
#include <memory>
#include <vector>
#include <unordered_map>
#include <mutex>

// Forward declarations
namespace inference {
class ModelInferRequest;
class ModelInferResponse;
}

namespace anyserve {

/**
 * WorkerClient - 与 Python Workers 通信的客户端
 *
 * 通过 Unix Domain Socket 向 Python Workers 转发推理请求。
 * 使用连接池优化性能。
 */
class WorkerClient {
public:
    WorkerClient();
    ~WorkerClient();

    /**
     * 转发推理请求到 Worker
     *
     * @param worker_address Worker 地址（格式："unix:///path/to/socket"）
     * @param request KServe v2 ModelInferRequest
     * @param response 输出参数，存储 Worker 返回的响应
     * @return 是否成功
     */
    bool forward_request(
        const std::string& worker_address,
        const inference::ModelInferRequest& request,
        inference::ModelInferResponse& response
    );

private:
    /**
     * Unix Socket 连接包装
     */
    struct Connection {
        int fd = -1;
        std::string socket_path;

        Connection() = default;
        explicit Connection(const std::string& path);
        ~Connection();

        // 禁止拷贝
        Connection(const Connection&) = delete;
        Connection& operator=(const Connection&) = delete;

        // 允许移动
        Connection(Connection&& other) noexcept;
        Connection& operator=(Connection&& other) noexcept;

        bool is_valid() const { return fd >= 0; }
        void close();
    };

    /**
     * 连接池
     */
    struct ConnectionPool {
        std::vector<std::unique_ptr<Connection>> available;
        size_t in_use = 0;
        size_t max_connections = 10;

        ConnectionPool() = default;
        ConnectionPool(ConnectionPool&&) = default;
        ConnectionPool& operator=(ConnectionPool&&) = default;

        // 禁止拷贝
        ConnectionPool(const ConnectionPool&) = delete;
        ConnectionPool& operator=(const ConnectionPool&) = delete;

        std::unique_ptr<Connection> acquire(const std::string& socket_path);
        void release(std::unique_ptr<Connection> conn);
    };

    /**
     * 发送请求数据
     *
     * @param conn 连接
     * @param data 数据
     * @return 是否成功
     */
    bool send_data(Connection& conn, const std::string& data);

    /**
     * 接收响应数据
     *
     * @param conn 连接
     * @param data 输出参数，存储接收到的数据
     * @return 是否成功
     */
    bool recv_data(Connection& conn, std::string& data);

    /**
     * 提取 socket 路径（去掉 "unix://" 前缀）
     */
    static std::string extract_socket_path(const std::string& worker_address);

    mutable std::mutex mutex_;
    std::unordered_map<std::string, ConnectionPool> pools_;

    // 统计信息
    size_t total_requests_ = 0;
    size_t failed_requests_ = 0;
};

} // namespace anyserve
