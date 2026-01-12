/**
 * main_v2.cpp - AnyServe Dispatcher 独立可执行文件
 *
 * 新架构：C++ Dispatcher 作为独立主进程
 *
 * 用法：
 *   anyserve_node --port 8000 --management-port 9000
 *
 * 功能：
 * 1. 启动 KServe v2 gRPC 服务器（接收推理请求）
 * 2. 启动 Worker Management gRPC 服务器（接收 Worker 注册）
 * 3. 根据 model_name 路由请求到 Python Workers
 * 4. Model 不存在时直接返回 NOT_FOUND
 */

#include <iostream>
#include <string>
#include <csignal>
#include <atomic>

#include "anyserve_dispatcher.hpp"

namespace {

std::atomic<bool> g_shutdown_requested{false};
anyserve::AnyserveDispatcher* g_ingress = nullptr;

void signal_handler(int signal) {
    std::cout << "\n[Main] Received signal " << signal << ", shutting down..." << std::endl;
    g_shutdown_requested = true;

    if (g_ingress) {
        g_ingress->stop();
    }
}

void print_usage(const char* program) {
    std::cerr << "Usage: " << program << " [OPTIONS]\n"
              << "\n"
              << "Options:\n"
              << "  --port PORT             KServe gRPC server port (default: 8000)\n"
              << "  --management-port PORT  Worker management port (default: 9000)\n"
              << "  --help                  Show this help message\n"
              << "\n"
              << "Example:\n"
              << "  " << program << " --port 8000 --management-port 9000\n"
              << std::endl;
}

} // anonymous namespace

int main(int argc, char** argv) {
    // 解析命令行参数
    int port = 8000;
    int management_port = 9000;

    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "--help" || arg == "-h") {
            print_usage(argv[0]);
            return 0;
        } else if (arg == "--port" && i + 1 < argc) {
            port = std::stoi(argv[++i]);
        } else if (arg == "--management-port" && i + 1 < argc) {
            management_port = std::stoi(argv[++i]);
        } else {
            std::cerr << "[Main] Unknown option: " << arg << std::endl;
            print_usage(argv[0]);
            return 1;
        }
    }

    // 设置信号处理
    std::signal(SIGINT, signal_handler);
    std::signal(SIGTERM, signal_handler);

    try {
        std::cout << "============================================" << std::endl;
        std::cout << "  AnyServe Dispatcher v0.2.0" << std::endl;
        std::cout << "============================================" << std::endl;
        std::cout << std::endl;

        // 创建 Dispatcher
        anyserve::AnyserveDispatcher ingress(port, management_port);
        g_ingress = &ingress;

        std::cout << "[Main] Starting Dispatcher..." << std::endl;
        std::cout << "[Main] KServe gRPC: 0.0.0.0:" << port << std::endl;
        std::cout << "[Main] Management:  0.0.0.0:" << management_port << std::endl;
        std::cout << "[Main] Press Ctrl+C to stop" << std::endl;
        std::cout << std::endl;

        // 运行 Dispatcher（阻塞）
        ingress.run();

        std::cout << "[Main] Dispatcher stopped" << std::endl;
        return 0;

    } catch (const std::exception& e) {
        std::cerr << "[Main] Error: " << e.what() << std::endl;
        return 1;
    }
}
