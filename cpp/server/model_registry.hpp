#pragma once

#include <string>
#include <unordered_map>
#include <mutex>
#include <optional>
#include <vector>

namespace anyserve {

/**
 * ModelRegistry - 维护 model → worker 的映射关系
 *
 * 线程安全的注册表，用于：
 * 1. Worker 注册模型
 * 2. Ingress 查找模型对应的 Worker
 * 3. Worker 下线时清理注册
 */
class ModelRegistry {
public:
    /**
     * 注册模型到 Worker
     * @param model_name 模型名称
     * @param model_version 模型版本（空字符串表示无版本）
     * @param worker_address Worker 地址（例如 "unix:///tmp/worker.sock"）
     * @param worker_id Worker 唯一标识
     */
    void register_model(const std::string& model_name,
                       const std::string& model_version,
                       const std::string& worker_address,
                       const std::string& worker_id);

    /**
     * 查找模型对应的 Worker 地址
     * @param model_name 模型名称
     * @param model_version 模型版本（空字符串表示无版本）
     * @return Worker 地址，如果未找到则返回 std::nullopt
     */
    std::optional<std::string> lookup_worker(const std::string& model_name,
                                             const std::string& model_version);

    /**
     * 注销指定 Worker 的所有模型
     * @param worker_id Worker 唯一标识
     * @return 注销的模型数量
     */
    size_t unregister_worker(const std::string& worker_id);

    /**
     * 注销指定模型
     * @param model_name 模型名称
     * @param model_version 模型版本
     * @param worker_id Worker 唯一标识
     * @return 是否成功注销
     */
    bool unregister_model(const std::string& model_name,
                         const std::string& model_version,
                         const std::string& worker_id);

    /**
     * 获取所有已注册的模型列表
     * @return 模型键列表（格式："name:version"）
     */
    std::vector<std::string> list_models() const;

    /**
     * 获取指定 Worker 的所有模型
     * @param worker_id Worker 唯一标识
     * @return 模型键列表
     */
    std::vector<std::string> list_models_by_worker(const std::string& worker_id) const;

private:
    /**
     * 生成模型键（name:version）
     */
    static std::string make_model_key(const std::string& name, const std::string& version) {
        if (version.empty()) {
            return name;
        }
        return name + ":" + version;
    }

    mutable std::mutex mutex_;

    // 主索引：model_key → worker_address
    std::unordered_map<std::string, std::string> model_to_worker_;

    // 反向索引：worker_id → set<model_key>
    std::unordered_map<std::string, std::vector<std::string>> worker_to_models_;

    // Worker 地址缓存：worker_id → worker_address
    std::unordered_map<std::string, std::string> worker_addresses_;
};

} // namespace anyserve
