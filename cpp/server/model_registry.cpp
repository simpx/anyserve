#include "model_registry.hpp"
#include <iostream>
#include <algorithm>

namespace anyserve {

void ModelRegistry::register_model(const std::string& model_name,
                                   const std::string& model_version,
                                   const std::string& worker_address,
                                   const std::string& worker_id) {
    std::lock_guard<std::mutex> lock(mutex_);

    std::string model_key = make_model_key(model_name, model_version);

    // 更新主索引
    model_to_worker_[model_key] = worker_address;

    // 更新反向索引
    auto& models = worker_to_models_[worker_id];
    if (std::find(models.begin(), models.end(), model_key) == models.end()) {
        models.push_back(model_key);
    }

    // 缓存 Worker 地址
    worker_addresses_[worker_id] = worker_address;

    std::cout << "[ModelRegistry] Registered: " << model_key
              << " -> " << worker_address
              << " (worker_id=" << worker_id << ")" << std::endl;
}

std::optional<std::string> ModelRegistry::lookup_worker(const std::string& model_name,
                                                        const std::string& model_version) {
    std::lock_guard<std::mutex> lock(mutex_);

    // 1. 尝试精确匹配（name:version）
    std::string model_key = make_model_key(model_name, model_version);
    std::cout << "[ModelRegistry] Lookup: " << model_key << std::endl;
    auto it = model_to_worker_.find(model_key);
    if (it != model_to_worker_.end()) {
        std::cout << "[ModelRegistry] Found: " << it->second << std::endl;
        return it->second;
    }

    // 2. 如果指定了版本但没找到，尝试无版本匹配
    if (!model_version.empty()) {
        std::string fallback_key = make_model_key(model_name, "");
        std::cout << "[ModelRegistry] Trying fallback: " << fallback_key << std::endl;
        auto fallback_it = model_to_worker_.find(fallback_key);
        if (fallback_it != model_to_worker_.end()) {
            std::cout << "[ModelRegistry] Found via fallback: " << fallback_it->second << std::endl;
            return fallback_it->second;
        }
    }

    std::cout << "[ModelRegistry] Not found" << std::endl;
    return std::nullopt;
}

size_t ModelRegistry::unregister_worker(const std::string& worker_id) {
    std::lock_guard<std::mutex> lock(mutex_);

    size_t count = 0;

    // 查找该 Worker 的所有模型
    auto worker_it = worker_to_models_.find(worker_id);
    if (worker_it != worker_to_models_.end()) {
        // 从主索引中移除所有模型
        for (const auto& model_key : worker_it->second) {
            model_to_worker_.erase(model_key);
            count++;
            std::cout << "[ModelRegistry] Unregistered: " << model_key
                      << " (worker_id=" << worker_id << ")" << std::endl;
        }

        // 移除反向索引
        worker_to_models_.erase(worker_it);
    }

    // 移除地址缓存
    worker_addresses_.erase(worker_id);

    std::cout << "[ModelRegistry] Worker " << worker_id
              << " unregistered (" << count << " models)" << std::endl;

    return count;
}

bool ModelRegistry::unregister_model(const std::string& model_name,
                                     const std::string& model_version,
                                     const std::string& worker_id) {
    std::lock_guard<std::mutex> lock(mutex_);

    std::string model_key = make_model_key(model_name, model_version);

    // 从主索引移除
    auto model_it = model_to_worker_.find(model_key);
    if (model_it == model_to_worker_.end()) {
        return false;
    }

    model_to_worker_.erase(model_it);

    // 从反向索引移除
    auto worker_it = worker_to_models_.find(worker_id);
    if (worker_it != worker_to_models_.end()) {
        auto& models = worker_it->second;
        models.erase(std::remove(models.begin(), models.end(), model_key), models.end());

        // 如果 Worker 没有模型了，移除 Worker
        if (models.empty()) {
            worker_to_models_.erase(worker_it);
            worker_addresses_.erase(worker_id);
        }
    }

    std::cout << "[ModelRegistry] Unregistered: " << model_key
              << " (worker_id=" << worker_id << ")" << std::endl;

    return true;
}

std::vector<std::string> ModelRegistry::list_models() const {
    std::lock_guard<std::mutex> lock(mutex_);

    std::vector<std::string> models;
    models.reserve(model_to_worker_.size());

    for (const auto& [model_key, _] : model_to_worker_) {
        models.push_back(model_key);
    }

    return models;
}

std::vector<std::string> ModelRegistry::list_models_by_worker(const std::string& worker_id) const {
    std::lock_guard<std::mutex> lock(mutex_);

    auto it = worker_to_models_.find(worker_id);
    if (it != worker_to_models_.end()) {
        return it->second;
    }

    return {};
}

} // namespace anyserve
