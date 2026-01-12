#pragma once

#include <string>
#include <vector>
#include <memory>
#include <functional>
#include <atomic>
#include <thread>
#include <mutex>
#include <unordered_map>
#include <unordered_set>

#include "shm_manager.hpp"
#include "process_supervisor.hpp"

// Forward declarations for gRPC types
namespace grpc {
class Server;
class ServerCompletionQueue;
class Channel;
}

namespace inference {
class GRPCInferenceService;
}

namespace anyserve {

/**
 * DispatcherCallback - Python dispatcher 回调接口
 * 
 * 当收到请求时，控制平面调用此回调让 Python 侧执行具体逻辑。
 */
using DispatcherCallback = std::function<std::string(
    const std::string& capability,
    const std::string& args_pickle,
    bool is_delegated
)>;

/**
 * AnyserveCore - 核心控制平面
 * 
 * 职责：
 * 1. gRPC 服务器（接收外部请求）
 * 2. gRPC 客户端（连接 Python Worker、远程调用）
 * 3. Capability 注册与发现
 * 4. SHM 管理（大对象传输）
 * 5. Python Worker 进程管理
 */
class AnyserveCore {
public:
    /**
     * 构造函数
     * @param root_dir 根目录（用于存储状态、发现）
     * @param instance_id 实例唯一标识
     * @param port gRPC 服务端口（0 = 随机分配）
     */
    AnyserveCore(const std::string& root_dir, 
                 const std::string& instance_id,
                 int port);
    
    ~AnyserveCore();

    // 禁止拷贝
    AnyserveCore(const AnyserveCore&) = delete;
    AnyserveCore& operator=(const AnyserveCore&) = delete;

    /**
     * 设置 Dispatcher 回调（Python 侧的请求处理器）
     */
    void set_dispatcher(DispatcherCallback callback);

    /**
     * 注册本地 capability
     * @param name capability 名称
     */
    void register_capability(const std::string& name);

    /**
     * 查找提供指定 capability 的端点列表
     * @param name capability 名称
     * @return 端点地址列表
     */
    std::vector<std::string> lookup_capability(const std::string& name);

    /**
     * 远程调用
     * @param address 目标地址
     * @param capability capability 名称
     * @param args_pickle 序列化的参数
     * @param is_delegated 是否为委托请求
     * @return 序列化的结果
     */
    std::string remote_call(const std::string& address,
                            const std::string& capability,
                            const std::string& args_pickle,
                            bool is_delegated);

    /**
     * 获取本实例的地址
     */
    std::string get_address() const;

    /**
     * 启动服务（gRPC 服务器、Worker 等）
     */
    void start();

    /**
     * 停止服务
     */
    void stop();

    /**
     * 检查是否正在运行
     */
    bool is_running() const { return running_.load(); }

    /**
     * 获取实例 ID
     */
    const std::string& instance_id() const { return instance_id_; }

    /**
     * 获取端口
     */
    int port() const { return port_; }

private:
    // 配置
    std::string root_dir_;
    std::string instance_id_;
    int port_;
    std::string address_;

    // 状态
    std::atomic<bool> running_{false};

    // SHM
    static constexpr size_t SHM_SIZE = 10 * 1024 * 1024; // 10MB
    ShmManager::RawShm shm_h2d_; // Host to Device
    ShmManager::RawShm shm_d2h_; // Device to Host

    // Capability 注册表（简单 PoC：使用文件系统做服务发现）
    mutable std::mutex capabilities_mutex_;
    std::unordered_set<std::string> local_capabilities_;

    // Dispatcher 回调
    DispatcherCallback dispatcher_;

    // gRPC 服务器
    std::unique_ptr<grpc::Server> server_;
    std::unique_ptr<grpc::ServerCompletionQueue> cq_;
    std::thread server_thread_;

    // gRPC 客户端连接池（简单 PoC：按需创建）
    mutable std::mutex clients_mutex_;
    std::unordered_map<std::string, std::shared_ptr<grpc::Channel>> client_channels_;

    // 辅助方法
    void run_server();
    void register_to_scheduler();
    void unregister_from_scheduler();
    std::shared_ptr<grpc::Channel> get_or_create_channel(const std::string& address);
};

} // namespace anyserve
