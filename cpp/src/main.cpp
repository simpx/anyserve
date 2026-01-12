/**
 * main.cpp - 独立可执行文件入口
 * 
 * 用法: anyserve_node [--port PORT] [APP_TARGET]
 * 
 * 这个可执行文件用于：
 * 1. 作为独立的 gRPC 代理服务器
 * 2. 派生和管理 Python Worker 进程
 * 3. 在 Python Worker 和外部客户端之间中转请求
 */

#include <iostream>
#include <string>
#include <csignal>
#include <atomic>

#include "anyserve_core.hpp"
#include "process_supervisor.hpp"
#include "shm_manager.hpp"

#include <grpcpp/grpcpp.h>
#include "grpc_predict_v2.grpc.pb.h"

namespace {

std::atomic<bool> g_shutdown_requested{false};

void signal_handler(int signal) {
    std::cout << "\n[main] Received signal " << signal << ", shutting down..." << std::endl;
    g_shutdown_requested = true;
}

void print_usage(const char* program) {
    std::cerr << "Usage: " << program << " [OPTIONS] [APP_TARGET]\n"
              << "\n"
              << "Options:\n"
              << "  --port PORT    gRPC server port (default: 8080)\n"
              << "  --help         Show this help message\n"
              << "\n"
              << "Arguments:\n"
              << "  APP_TARGET     Python app target (e.g., 'myapp:app')\n"
              << std::endl;
}

} // anonymous namespace

int main(int argc, char** argv) {
    // 解析命令行参数
    std::string app_target;
    int port = 8080;
    
    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "--help" || arg == "-h") {
            print_usage(argv[0]);
            return 0;
        } else if (arg == "--port" && i + 1 < argc) {
            port = std::stoi(argv[++i]);
        } else if (!arg.empty() && arg[0] != '-') {
            app_target = arg;
        }
    }
    
    // 设置信号处理
    std::signal(SIGINT, signal_handler);
    std::signal(SIGTERM, signal_handler);
    
    try {
        // 1. 创建 SHM
        auto shm_h2d = anyserve::ShmManager::create(10 * 1024 * 1024);
        auto shm_d2h = anyserve::ShmManager::create(10 * 1024 * 1024);
        std::cout << "[main] Created SHM. H2D_FD=" << shm_h2d.fd 
                  << ", D2H_FD=" << shm_d2h.fd << std::endl;
        
        // 2. 生成随机 UDS 路径
        std::srand(static_cast<unsigned>(std::time(nullptr)));
        std::string uds_path = "/tmp/anyserve_" + std::to_string(std::rand()) + ".sock";
        std::cout << "[main] Using UDS path: " << uds_path << std::endl;
        
        // 3. 派生 Python Worker
        std::string python_path = std::getenv("PYTHON_PATH") ? std::getenv("PYTHON_PATH") : "python";
        std::string worker_module = "anyserve_worker.loader";
        
        anyserve::ProcessSupervisor supervisor(python_path, worker_module);
        
        std::vector<std::string> extra_args;
        if (!app_target.empty()) {
            extra_args.push_back(app_target);
        }
        
        supervisor.spawn(uds_path, shm_h2d.fd, shm_d2h.fd, extra_args);
        std::cout << "[main] Worker spawned. Waiting for ready..." << std::endl;
        
        if (!supervisor.wait_for_ready(10)) {
            std::cerr << "[main] Worker failed to start within timeout" << std::endl;
            return 1;
        }
        std::cout << "[main] Worker ready." << std::endl;
        
        // 4. 连接到 Worker
        std::string worker_address = "unix://" + uds_path;
        auto channel = grpc::CreateChannel(worker_address, grpc::InsecureChannelCredentials());
        auto stub = inference::GRPCInferenceService::NewStub(channel);
        
        // 等待 channel 连接就绪
        auto deadline = std::chrono::system_clock::now() + std::chrono::seconds(5);
        if (!channel->WaitForConnected(deadline)) {
            std::cerr << "[main] Failed to connect to worker" << std::endl;
            return 1;
        }
        std::cout << "[main] Connected to Worker via UDS" << std::endl;
        
        // 5. 启动代理 gRPC 服务器
        std::string server_address = "0.0.0.0:" + std::to_string(port);
        
        // 简单代理服务实现
        class ProxyService final : public inference::GRPCInferenceService::Service {
        public:
            explicit ProxyService(std::unique_ptr<inference::GRPCInferenceService::Stub> stub)
                : stub_(std::move(stub)) {}
            
            grpc::Status ServerLive(
                grpc::ServerContext* context,
                const inference::ServerLiveRequest* request,
                inference::ServerLiveResponse* response) override {
                grpc::ClientContext client_ctx;
                return stub_->ServerLive(&client_ctx, *request, response);
            }
            
            grpc::Status ServerReady(
                grpc::ServerContext* context,
                const inference::ServerReadyRequest* request,
                inference::ServerReadyResponse* response) override {
                grpc::ClientContext client_ctx;
                return stub_->ServerReady(&client_ctx, *request, response);
            }
            
            grpc::Status ModelReady(
                grpc::ServerContext* context,
                const inference::ModelReadyRequest* request,
                inference::ModelReadyResponse* response) override {
                grpc::ClientContext client_ctx;
                return stub_->ModelReady(&client_ctx, *request, response);
            }
            
            grpc::Status ServerMetadata(
                grpc::ServerContext* context,
                const inference::ServerMetadataRequest* request,
                inference::ServerMetadataResponse* response) override {
                grpc::ClientContext client_ctx;
                return stub_->ServerMetadata(&client_ctx, *request, response);
            }
            
            grpc::Status ModelMetadata(
                grpc::ServerContext* context,
                const inference::ModelMetadataRequest* request,
                inference::ModelMetadataResponse* response) override {
                grpc::ClientContext client_ctx;
                return stub_->ModelMetadata(&client_ctx, *request, response);
            }
            
            grpc::Status ModelInfer(
                grpc::ServerContext* context,
                const inference::ModelInferRequest* request,
                inference::ModelInferResponse* response) override {
                grpc::ClientContext client_ctx;
                client_ctx.set_deadline(std::chrono::system_clock::now() + std::chrono::seconds(60));
                return stub_->ModelInfer(&client_ctx, *request, response);
            }
            
        private:
            std::unique_ptr<inference::GRPCInferenceService::Stub> stub_;
        };
        
        ProxyService proxy_service(std::move(stub));
        
        grpc::ServerBuilder builder;
        builder.AddListeningPort(server_address, grpc::InsecureServerCredentials());
        builder.RegisterService(&proxy_service);
        
        auto server = builder.BuildAndStart();
        if (!server) {
            std::cerr << "[main] Failed to start gRPC server" << std::endl;
            return 1;
        }
        
        std::cout << "[main] gRPC server listening on " << server_address << std::endl;
        
        // 6. 主循环
        while (!g_shutdown_requested) {
            // 检查 Worker 是否存活
            if (!supervisor.is_alive()) {
                std::cerr << "[main] Worker process exited unexpectedly" << std::endl;
                break;
            }
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
        }
        
        // 7. 清理
        std::cout << "[main] Shutting down..." << std::endl;
        server->Shutdown();
        supervisor.stop();
        
        // 删除 UDS 文件
        std::remove(uds_path.c_str());
        
        std::cout << "[main] Done." << std::endl;
        return 0;
        
    } catch (const std::exception& e) {
        std::cerr << "[main] Error: " << e.what() << std::endl;
        return 1;
    }
}
