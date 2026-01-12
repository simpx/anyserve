#pragma once

#include <string>
#include <sys/types.h>

namespace anyserve {

/**
 * ProcessSupervisor - Python Worker 进程管理器
 * 
 * 负责：
 * 1. 派生 Python Worker 子进程
 * 2. 通过 pipe 接收就绪信号
 * 3. 传递环境变量（UDS 路径、SHM fd 等）
 * 4. 进程生命周期管理
 */
class ProcessSupervisor {
public:
    /**
     * 构造函数
     * @param python_path Python 可执行文件路径
     * @param worker_module Python 模块名（通过 -m 启动）
     */
    ProcessSupervisor(const std::string& python_path, const std::string& worker_module);
    
    ~ProcessSupervisor();

    // 禁止拷贝
    ProcessSupervisor(const ProcessSupervisor&) = delete;
    ProcessSupervisor& operator=(const ProcessSupervisor&) = delete;

    /**
     * 派生 Worker 进程
     * @param uds_path Unix Domain Socket 路径
     * @param h2d_fd Host-to-Device SHM fd
     * @param d2h_fd Device-to-Host SHM fd
     * @throws std::runtime_error 如果 fork 失败
     */
    void spawn(const std::string& uds_path, int h2d_fd, int d2h_fd);

    /**
     * 派生 Worker 进程（带额外参数）
     * @param uds_path Unix Domain Socket 路径
     * @param h2d_fd Host-to-Device SHM fd
     * @param d2h_fd Device-to-Host SHM fd
     * @param extra_args 额外命令行参数
     * @throws std::runtime_error 如果 fork 失败
     */
    void spawn(const std::string& uds_path, int h2d_fd, int d2h_fd, 
               const std::vector<std::string>& extra_args);

    /**
     * 等待 Worker 就绪信号
     * @param timeout_seconds 超时秒数
     * @return true 如果收到就绪信号，false 如果超时
     */
    bool wait_for_ready(int timeout_seconds);

    /**
     * 停止 Worker 进程
     */
    void stop();

    /**
     * 检查 Worker 是否存活
     */
    bool is_alive() const;

    /**
     * 获取 Worker PID
     */
    pid_t get_pid() const { return worker_pid_; }

private:
    std::string python_path_;
    std::string worker_module_;
    pid_t worker_pid_ = -1;
    int read_fd_ = -1;
    int write_fd_ = -1;
};

} // namespace anyserve
