#include "anyserve_dispatcher.hpp"

#include <iostream>
#include <fstream>
#include <ctime>
#include <grpcpp/grpcpp.h>

#include "grpc_predict_v2.grpc.pb.h"
#include "worker_management.grpc.pb.h"

namespace anyserve {

// ============================================================================
// KServe v2 gRPC Service Implementation
// ============================================================================

class KServeServiceImpl final : public inference::GRPCInferenceService::Service {
public:
    explicit KServeServiceImpl(AnyserveDispatcher* ingress) : ingress_(ingress) {}

    grpc::Status ServerLive(
        grpc::ServerContext* context,
        const inference::ServerLiveRequest* request,
        inference::ServerLiveResponse* response) override {

        response->set_live(true);
        return grpc::Status::OK;
    }

    grpc::Status ServerReady(
        grpc::ServerContext* context,
        const inference::ServerReadyRequest* request,
        inference::ServerReadyResponse* response) override {

        response->set_ready(ingress_->is_running());
        return grpc::Status::OK;
    }

    grpc::Status ModelReady(
        grpc::ServerContext* context,
        const inference::ModelReadyRequest* request,
        inference::ModelReadyResponse* response) override {

        // 检查模型是否注册
        auto worker_addr = ingress_->get_registry().lookup_worker(
            request->name(),
            request->version()
        );

        response->set_ready(worker_addr.has_value());
        return grpc::Status::OK;
    }

    grpc::Status ServerMetadata(
        grpc::ServerContext* context,
        const inference::ServerMetadataRequest* request,
        inference::ServerMetadataResponse* response) override {

        response->set_name("anyserve-ingress");
        response->set_version("0.2.0");
        return grpc::Status::OK;
    }

    grpc::Status ModelMetadata(
        grpc::ServerContext* context,
        const inference::ModelMetadataRequest* request,
        inference::ModelMetadataResponse* response) override {

        response->set_name(request->name());
        response->set_platform("anyserve");

        // TODO: 可以从 Worker 获取更详细的 metadata
        return grpc::Status::OK;
    }

    grpc::Status ModelInfer(
        grpc::ServerContext* context,
        const inference::ModelInferRequest* request,
        inference::ModelInferResponse* response) override {

        // 写文件确认函数被调用
        {
            std::ofstream logfile("/tmp/anyserve_modelinfer.log", std::ios::app);
            logfile << "ModelInfer called at " << time(nullptr) << std::endl;
            logfile.close();
        }

        std::string model_name = request->model_name();
        std::string model_version = request->model_version();

        std::cerr << "\n========================================" << std::endl;
        std::cerr << "[KServeService] >>> ModelInfer called" << std::endl;
        std::cerr << "[KServeService]     model_name    = '" << model_name << "'" << std::endl;
        std::cerr << "[KServeService]     model_version = '" << model_version << "'" << std::endl;
        std::cerr << "[KServeService]     request_id    = '" << request->id() << "'" << std::endl;
        std::cerr << "========================================" << std::endl;
        std::cerr.flush();

        // 列出所有已注册的模型（用于调试）
        auto all_models = ingress_->get_registry().list_models();
        std::cerr << "[KServeService] Currently registered models (" << all_models.size() << "):" << std::endl;
        for (const auto& model : all_models) {
            std::cerr << "[KServeService]   - " << model << std::endl;
        }

        // 1. 查找 Worker
        std::cerr << "[KServeService] Looking up worker for: " << model_name;
        if (!model_version.empty()) {
            std::cerr << ":" << model_version;
        }
        std::cerr << std::endl;

        auto worker_addr = ingress_->get_registry().lookup_worker(model_name, model_version);

        if (!worker_addr.has_value()) {
            // Model 不存在，直接返回 NOT_FOUND（无需 Python）
            std::string error_msg = "Model '" + model_name;
            if (!model_version.empty()) {
                error_msg += ":" + model_version;
            }
            error_msg += "' not found";

            std::cerr << "[KServeService] ✗ Worker NOT FOUND!" << std::endl;
            std::cerr << "[KServeService] Returning NOT_FOUND: " << error_msg << std::endl;
            std::cerr << "========================================\n" << std::endl;
            std::cerr.flush();
            return grpc::Status(grpc::StatusCode::NOT_FOUND, error_msg);
        }

        std::cerr << "[KServeService] ✓ Found worker: " << worker_addr.value() << std::endl;

        // 2. 转发请求到 Worker
        std::cerr << "[KServeService] Forwarding request to worker..." << std::endl;
        bool success = ingress_->get_worker_client().forward_request(
            worker_addr.value(),
            *request,
            *response
        );

        if (!success) {
            std::cerr << "[KServeService] ✗ Failed to forward request to worker" << std::endl;
            std::cerr << "========================================\n" << std::endl;
            std::cerr.flush();
            return grpc::Status(
                grpc::StatusCode::INTERNAL,
                "Failed to forward request to worker"
            );
        }

        std::cerr << "[KServeService] ✓ Request forwarded successfully" << std::endl;
        std::cerr << "[KServeService] Response has " << response->outputs_size() << " outputs" << std::endl;
        std::cerr << "[KServeService] Returning OK" << std::endl;
        std::cerr << "========================================\n" << std::endl;
        std::cerr.flush();
        return grpc::Status::OK;
    }

private:
    AnyserveDispatcher* ingress_;
};

// ============================================================================
// Worker Management gRPC Service Implementation
// ============================================================================

class WorkerManagementServiceImpl final : public anyserve::WorkerManagement::Service {
public:
    explicit WorkerManagementServiceImpl(AnyserveDispatcher* ingress) : ingress_(ingress) {}

    grpc::Status RegisterModel(
        grpc::ServerContext* context,
        const anyserve::RegisterModelRequest* request,
        anyserve::RegisterModelResponse* response) override {

        try {
            ingress_->get_registry().register_model(
                request->model_name(),
                request->model_version(),
                request->worker_address(),
                request->worker_id()
            );

            response->set_success(true);
            response->set_message("Model registered successfully");

        } catch (const std::exception& e) {
            response->set_success(false);
            response->set_message(e.what());
            return grpc::Status(grpc::StatusCode::INTERNAL, e.what());
        }

        return grpc::Status::OK;
    }

    grpc::Status UnregisterModel(
        grpc::ServerContext* context,
        const anyserve::UnregisterModelRequest* request,
        anyserve::UnregisterModelResponse* response) override {

        bool success = ingress_->get_registry().unregister_model(
            request->model_name(),
            request->model_version(),
            request->worker_id()
        );

        response->set_success(success);
        if (success) {
            response->set_message("Model unregistered successfully");
        } else {
            response->set_message("Model not found");
        }

        return grpc::Status::OK;
    }

    grpc::Status Heartbeat(
        grpc::ServerContext* context,
        const anyserve::HeartbeatRequest* request,
        anyserve::HeartbeatResponse* response) override {

        // TODO: 实现真正的健康检查逻辑
        response->set_healthy(true);
        return grpc::Status::OK;
    }

private:
    AnyserveDispatcher* ingress_;
};

// ============================================================================
// AnyserveDispatcher Implementation
// ============================================================================

AnyserveDispatcher::AnyserveDispatcher(int port, int management_port)
    : port_(port), management_port_(management_port) {

    std::cout << "[AnyserveDispatcher] Initialized" << std::endl;
    std::cout << "[AnyserveDispatcher] KServe port: " << port_ << std::endl;
    std::cout << "[AnyserveDispatcher] Management port: " << management_port_ << std::endl;
}

AnyserveDispatcher::~AnyserveDispatcher() {
    stop();
}

void AnyserveDispatcher::run() {
    running_.store(true);

    // 启动 KServe 服务器（独立线程）
    server_thread_ = std::thread(&AnyserveDispatcher::run_server, this);

    // 启动 Worker 管理服务器（独立线程）
    management_thread_ = std::thread(&AnyserveDispatcher::run_management_server, this);

    // 等待线程
    if (server_thread_.joinable()) {
        server_thread_.join();
    }
    if (management_thread_.joinable()) {
        management_thread_.join();
    }
}

void AnyserveDispatcher::stop() {
    if (running_.exchange(false)) {
        std::cout << "[AnyserveDispatcher] Stopping..." << std::endl;

        if (server_) {
            server_->Shutdown();
        }
        if (management_server_) {
            management_server_->Shutdown();
        }
    }
}

void AnyserveDispatcher::run_server() {
    KServeServiceImpl service(this);

    std::string server_address = "0.0.0.0:" + std::to_string(port_);

    grpc::ServerBuilder builder;
    builder.AddListeningPort(server_address, grpc::InsecureServerCredentials());
    builder.RegisterService(&service);

    server_ = builder.BuildAndStart();

    std::cout << "[AnyserveDispatcher] KServe gRPC server listening on " << server_address << std::endl;

    if (server_) {
        server_->Wait();
    }
}

void AnyserveDispatcher::run_management_server() {
    WorkerManagementServiceImpl service(this);

    std::string server_address = "0.0.0.0:" + std::to_string(management_port_);

    grpc::ServerBuilder builder;
    builder.AddListeningPort(server_address, grpc::InsecureServerCredentials());
    builder.RegisterService(&service);

    management_server_ = builder.BuildAndStart();

    std::cout << "[AnyserveDispatcher] Worker Management server listening on " << server_address << std::endl;

    if (management_server_) {
        management_server_->Wait();
    }
}

} // namespace anyserve
