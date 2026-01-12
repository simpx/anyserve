#pragma once

#include <string>
#include <memory>
#include <atomic>
#include <thread>

#include "model_registry.hpp"
#include "worker_client.hpp"

// Forward declarations for gRPC types
namespace grpc {
class Server;
class ServerCompletionQueue;
}

namespace anyserve {

/**
 * AnyserveIngress - C++ Ingress 主类
 *
 * 核心职责：
 * 1. 接收外部 KServe v2 gRPC 请求
 * 2. 根据 model_name 路由到对应的 Python Worker
 * 3. 提供 Worker 注册/注销 API
 * 4. Model 不存在时直接返回错误（无需 Python）
 */
class AnyserveIngress {
public:
    /**
     * 构造函数
     *
     * @param port gRPC 服务端口（KServe v2）
     * @param management_port Worker 管理端口
     */
    AnyserveIngress(int port, int management_port);

    ~AnyserveIngress();

    // 禁止拷贝
    AnyserveIngress(const AnyserveIngress&) = delete;
    AnyserveIngress& operator=(const AnyserveIngress&) = delete;

    /**
     * 启动 Ingress（阻塞）
     */
    void run();

    /**
     * 停止 Ingress
     */
    void stop();

    /**
     * 检查是否正在运行
     */
    bool is_running() const { return running_.load(); }

    /**
     * 获取 Model Registry
     */
    ModelRegistry& get_registry() { return registry_; }

    /**
     * 获取 Worker Client
     */
    WorkerClient& get_worker_client() { return worker_client_; }

    /**
     * 获取端口
     */
    int port() const { return port_; }
    int management_port() const { return management_port_; }

private:
    /**
     * 运行 gRPC 服务器（内部线程）
     */
    void run_server();

    /**
     * 运行 Worker 管理服务器（内部线程）
     */
    void run_management_server();

    int port_;
    int management_port_;

    std::atomic<bool> running_{false};

    // 核心组件
    ModelRegistry registry_;
    WorkerClient worker_client_;

    // gRPC 服务器
    std::unique_ptr<grpc::Server> server_;
    std::unique_ptr<grpc::Server> management_server_;

    std::thread server_thread_;
    std::thread management_thread_;
};

} // namespace anyserve
