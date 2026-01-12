#include "anyserve_core.hpp"

#include <iostream>
#include <fstream>
#include <filesystem>
#include <random>
#include <chrono>

#include <grpcpp/grpcpp.h>
#include "grpc_predict_v2.grpc.pb.h"

namespace fs = std::filesystem;

namespace anyserve {

// ============================================================================
// gRPC Service Implementation (Async)
// ============================================================================

class GrpcServiceImpl final : public inference::GRPCInferenceService::Service {
public:
    explicit GrpcServiceImpl(AnyserveCore* core) : core_(core) {}

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
        response->set_ready(core_->is_running());
        return grpc::Status::OK;
    }

    grpc::Status ModelReady(
        grpc::ServerContext* context,
        const inference::ModelReadyRequest* request,
        inference::ModelReadyResponse* response) override {
        response->set_ready(true);
        return grpc::Status::OK;
    }

    grpc::Status ServerMetadata(
        grpc::ServerContext* context,
        const inference::ServerMetadataRequest* request,
        inference::ServerMetadataResponse* response) override {
        response->set_name("anyserve");
        response->set_version("0.1.0");
        return grpc::Status::OK;
    }

    grpc::Status ModelMetadata(
        grpc::ServerContext* context,
        const inference::ModelMetadataRequest* request,
        inference::ModelMetadataResponse* response) override {
        response->set_name(request->name());
        response->set_platform("anyserve");
        return grpc::Status::OK;
    }

    grpc::Status ModelInfer(
        grpc::ServerContext* context,
        const inference::ModelInferRequest* request,
        inference::ModelInferResponse* response) override {

        // KServe v2 协议：model_name 作为 capability
        std::string capability = request->model_name();

        // 将整个 ModelInferRequest 序列化为 protobuf bytes
        // 传递给 Python dispatcher（当前使用 pickle，未来改为 protobuf）
        std::string request_bytes;
        if (!request->SerializeToString(&request_bytes)) {
            return grpc::Status(grpc::StatusCode::INTERNAL, "Failed to serialize request");
        }

        // 检查是否为委托请求（通过 parameters）
        bool is_delegated = false;
        auto it = request->parameters().find("is_delegated");
        if (it != request->parameters().end()) {
            is_delegated = it->second.bool_param();
        }

        try {
            const auto& dispatcher = core_->get_dispatcher();
            if (!dispatcher) {
                return grpc::Status(grpc::StatusCode::UNIMPLEMENTED,
                                  "Dispatcher not set");
            }

            // 调用 Python dispatcher
            std::string response_bytes = dispatcher(
                capability,
                request_bytes,
                is_delegated
            );

            // 解析 Python 返回的 ModelInferResponse
            if (!response->ParseFromString(response_bytes)) {
                return grpc::Status(grpc::StatusCode::INTERNAL,
                                  "Failed to parse response from Python");
            }

            return grpc::Status::OK;

        } catch (const std::exception& e) {
            return grpc::Status(grpc::StatusCode::INTERNAL, e.what());
        }
    }

private:
    AnyserveCore* core_;
};

// ============================================================================
// AnyserveCore Implementation
// ============================================================================

AnyserveCore::AnyserveCore(const std::string& root_dir,
                           const std::string& instance_id,
                           int port)
    : root_dir_(root_dir), instance_id_(instance_id), port_(port) {
    
    // 如果端口为 0，随机选择一个
    if (port_ == 0) {
        std::random_device rd;
        std::mt19937 gen(rd());
        std::uniform_int_distribution<> dis(10000, 20000);
        port_ = dis(gen);
    }
    
    address_ = "localhost:" + std::to_string(port_);
    
    // 确保目录存在
    fs::create_directories(root_dir_);
    fs::create_directories(root_dir_ + "/instances");
    fs::create_directories(root_dir_ + "/names");
    
    // 创建 SHM
    try {
        shm_h2d_ = ShmManager::create(SHM_SIZE);
        shm_d2h_ = ShmManager::create(SHM_SIZE);
        std::cout << "[AnyserveCore] Created SHM. H2D_FD=" << shm_h2d_.fd 
                  << ", D2H_FD=" << shm_d2h_.fd << std::endl;
    } catch (const std::exception& e) {
        std::cerr << "[AnyserveCore] SHM creation failed: " << e.what() << std::endl;
        throw;
    }
    
    std::cout << "[AnyserveCore] Initialized. ID=" << instance_id_ 
              << ", Port=" << port_ << std::endl;
}

AnyserveCore::~AnyserveCore() {
    stop();
}

void AnyserveCore::set_dispatcher(DispatcherCallback callback) {
    dispatcher_ = std::move(callback);
}

void AnyserveCore::register_capability(const std::string& name) {
    {
        std::lock_guard<std::mutex> lock(capabilities_mutex_);
        local_capabilities_.insert(name);
    }
    
    // 注册到调度器（文件系统方式）
    std::string cap_dir = root_dir_ + "/names/" + name;
    fs::create_directories(cap_dir);
    
    std::string instance_file = cap_dir + "/" + instance_id_;
    std::ofstream ofs(instance_file);
    ofs << address_;
    ofs.close();
    
    std::cout << "[AnyserveCore] Registered capability: " << name << std::endl;
}

std::vector<std::string> AnyserveCore::lookup_capability(const std::string& name) {
    std::vector<std::string> endpoints;
    
    std::string cap_dir = root_dir_ + "/names/" + name;
    if (!fs::exists(cap_dir)) {
        return endpoints;
    }
    
    for (const auto& entry : fs::directory_iterator(cap_dir)) {
        if (entry.is_regular_file()) {
            std::ifstream ifs(entry.path());
            std::string address;
            std::getline(ifs, address);
            if (!address.empty()) {
                endpoints.push_back(address);
            }
        }
    }
    
    return endpoints;
}

std::string AnyserveCore::remote_call(const std::string& address,
                                       const std::string& capability,
                                       const std::string& args_pickle,
                                       bool is_delegated) {
    // 获取或创建 gRPC channel
    auto channel = get_or_create_channel(address);
    auto stub = inference::GRPCInferenceService::NewStub(channel);
    
    // 构建请求
    inference::ModelInferRequest request;
    request.set_model_name(capability);
    request.set_id(std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()));
    
    // 添加输入
    auto* input = request.add_inputs();
    input->set_name("args");
    input->set_datatype("BYTES");
    input->add_shape(static_cast<int64_t>(args_pickle.size()));
    
    request.add_raw_input_contents(args_pickle);
    
    // 设置委托标记
    if (is_delegated) {
        (*request.mutable_parameters())["is_delegated"].set_bool_param(true);
    }
    
    // 发起同步调用（PoC 简化）
    inference::ModelInferResponse response;
    grpc::ClientContext context;
    context.set_deadline(std::chrono::system_clock::now() + std::chrono::seconds(30));
    
    grpc::Status status = stub->ModelInfer(&context, request, &response);
    
    if (!status.ok()) {
        throw std::runtime_error("Remote call failed: " + status.error_message());
    }
    
    // 提取结果
    if (response.raw_output_contents_size() > 0) {
        return response.raw_output_contents(0);
    }
    
    return "";
}

std::string AnyserveCore::get_address() const {
    return address_;
}

void AnyserveCore::start() {
    if (running_.load()) {
        return;
    }
    
    running_ = true;
    
    // 启动 gRPC 服务器
    std::string server_address = "0.0.0.0:" + std::to_string(port_);
    
    auto service = std::make_unique<GrpcServiceImpl>(this);
    
    grpc::ServerBuilder builder;
    builder.AddListeningPort(server_address, grpc::InsecureServerCredentials());
    builder.RegisterService(service.get());
    
    server_ = builder.BuildAndStart();
    
    if (!server_) {
        running_ = false;
        throw std::runtime_error("Failed to start gRPC server on " + server_address);
    }
    
    std::cout << "[AnyserveCore] gRPC server listening on " << server_address << std::endl;
    
    // 在后台线程运行服务器
    server_thread_ = std::thread([this, svc = std::move(service)]() {
        server_->Wait();
    });
    
    // 注册实例
    register_to_scheduler();
}

void AnyserveCore::stop() {
    if (!running_.load()) {
        return;
    }
    
    running_ = false;
    
    // 注销实例
    unregister_from_scheduler();
    
    // 停止 gRPC 服务器
    if (server_) {
        server_->Shutdown();
    }
    
    if (server_thread_.joinable()) {
        server_thread_.join();
    }
    
    std::cout << "[AnyserveCore] Stopped." << std::endl;
}

void AnyserveCore::run_server() {
    // 用于 Async 模式的事件循环（当前使用 Sync 模式，此方法暂不使用）
}

void AnyserveCore::register_to_scheduler() {
    // 注册实例信息
    std::string instance_dir = root_dir_ + "/instances/" + instance_id_;
    fs::create_directories(instance_dir);
    
    std::ofstream ofs(instance_dir + "/address");
    ofs << address_;
    ofs.close();
    
    std::cout << "[AnyserveCore] Registered to scheduler." << std::endl;
}

void AnyserveCore::unregister_from_scheduler() {
    // 移除实例信息
    std::string instance_dir = root_dir_ + "/instances/" + instance_id_;
    fs::remove_all(instance_dir);
    
    // 移除 capability 注册
    std::lock_guard<std::mutex> lock(capabilities_mutex_);
    for (const auto& cap : local_capabilities_) {
        std::string cap_file = root_dir_ + "/names/" + cap + "/" + instance_id_;
        fs::remove(cap_file);
    }
    
    std::cout << "[AnyserveCore] Unregistered from scheduler." << std::endl;
}

std::shared_ptr<grpc::Channel> AnyserveCore::get_or_create_channel(const std::string& address) {
    std::lock_guard<std::mutex> lock(clients_mutex_);
    
    auto it = client_channels_.find(address);
    if (it != client_channels_.end()) {
        return it->second;
    }
    
    // 创建新 channel
    auto channel = grpc::CreateChannel(address, grpc::InsecureChannelCredentials());
    client_channels_[address] = channel;
    
    return channel;
}

} // namespace anyserve
