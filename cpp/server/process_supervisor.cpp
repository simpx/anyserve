#include "process_supervisor.hpp"

#include <iostream>
#include <vector>
#include <cstring>
#include <cstdlib>
#include <stdexcept>
#include <unistd.h>
#include <sys/wait.h>
#include <poll.h>
#include <signal.h>

namespace anyserve {

namespace {

void close_fd(int& fd) {
    if (fd >= 0) {
        close(fd);
        fd = -1;
    }
}

} // anonymous namespace

ProcessSupervisor::ProcessSupervisor(const std::string& python_path, const std::string& worker_module)
    : python_path_(python_path), worker_module_(worker_module) {}

ProcessSupervisor::~ProcessSupervisor() {
    stop();
    close_fd(read_fd_);
}

void ProcessSupervisor::spawn(const std::string& uds_path, int h2d_fd, int d2h_fd) {
    spawn(uds_path, h2d_fd, d2h_fd, {});
}

void ProcessSupervisor::spawn(const std::string& uds_path, int h2d_fd, int d2h_fd,
                               const std::vector<std::string>& extra_args) {
    // 创建 pipe 用于就绪信号
    int pipe_fds[2];
    if (pipe(pipe_fds) < 0) {
        throw std::runtime_error("Failed to create pipe: " + std::string(strerror(errno)));
    }
    read_fd_ = pipe_fds[0];
    write_fd_ = pipe_fds[1];

    pid_t pid = fork();
    if (pid < 0) {
        close_fd(read_fd_);
        close_fd(write_fd_);
        throw std::runtime_error("Fork failed: " + std::string(strerror(errno)));
    }

    if (pid == 0) {
        // ===== 子进程 =====
        close(read_fd_); // 子进程不读

        // 设置环境变量
        setenv("ANSERVE_WORKER_UDS", uds_path.c_str(), 1);
        setenv("ANSERVE_READY_FD", std::to_string(write_fd_).c_str(), 1);
        setenv("ANSERVE_H2D_FD", std::to_string(h2d_fd).c_str(), 1);
        setenv("ANSERVE_D2H_FD", std::to_string(d2h_fd).c_str(), 1);

        // 构建参数列表: python -m <module> [extra_args...]
        std::vector<char*> args;
        args.push_back(const_cast<char*>(python_path_.c_str()));
        args.push_back(const_cast<char*>("-m"));
        args.push_back(const_cast<char*>(worker_module_.c_str()));
        
        // 添加额外参数
        for (const auto& arg : extra_args) {
            args.push_back(const_cast<char*>(arg.c_str()));
        }
        args.push_back(nullptr);

        // 执行
        execvp(python_path_.c_str(), args.data());

        // 如果 execvp 返回，说明失败了
        std::cerr << "Failed to exec python worker: " << strerror(errno) << std::endl;
        _exit(1);
    } else {
        // ===== 父进程 =====
        worker_pid_ = pid;
        close(write_fd_); // 父进程不写
        write_fd_ = -1;
    }
}

bool ProcessSupervisor::wait_for_ready(int timeout_seconds) {
    if (read_fd_ < 0) {
        return false;
    }

    struct pollfd pfd;
    pfd.fd = read_fd_;
    pfd.events = POLLIN;

    int ret = poll(&pfd, 1, timeout_seconds * 1000);
    if (ret > 0) {
        if (pfd.revents & POLLIN) {
            char buf[128];
            ssize_t n = read(read_fd_, buf, sizeof(buf) - 1);
            if (n > 0) {
                buf[n] = '\0';
                std::cout << "[ProcessSupervisor] Worker signaled: " << buf << std::endl;
                return true;
            }
        }
    } else if (ret == 0) {
        std::cerr << "[ProcessSupervisor] Timeout waiting for worker ready" << std::endl;
    } else {
        std::cerr << "[ProcessSupervisor] Poll error: " << strerror(errno) << std::endl;
    }
    return false;
}

void ProcessSupervisor::stop() {
    if (worker_pid_ > 0) {
        // 先发送 SIGTERM
        kill(worker_pid_, SIGTERM);
        
        // 等待最多 5 秒
        int status;
        for (int i = 0; i < 50; ++i) {
            pid_t result = waitpid(worker_pid_, &status, WNOHANG);
            if (result == worker_pid_) {
                worker_pid_ = -1;
                return;
            }
            usleep(100000); // 100ms
        }
        
        // 超时则强制 SIGKILL
        kill(worker_pid_, SIGKILL);
        waitpid(worker_pid_, nullptr, 0);
        worker_pid_ = -1;
    }
}

bool ProcessSupervisor::is_alive() const {
    if (worker_pid_ <= 0) {
        return false;
    }
    
    // 检查进程是否存在
    int status;
    pid_t result = waitpid(worker_pid_, &status, WNOHANG);
    return result == 0; // 0 表示进程仍在运行
}

} // namespace anyserve
