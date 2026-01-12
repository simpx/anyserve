#pragma once

#include <string>
#include <cstddef>

namespace anyserve {

/**
 * ShmManager - POSIX 共享内存管理器
 * 
 * 用于在控制平面（C++）和执行平面（Python Worker）之间高效传输大数据块。
 * 使用匿名 SHM（创建后立即 unlink），通过 fd 继承传递给子进程。
 */
class ShmManager {
public:
    /**
     * RawShm - 单个共享内存段
     */
    struct RawShm {
        int fd = -1;
        void* ptr = nullptr;
        size_t size = 0;
        std::string name;

        RawShm() = default;
        RawShm(RawShm&& other) noexcept;
        RawShm& operator=(RawShm&& other) noexcept;
        ~RawShm();

        // 禁止拷贝
        RawShm(const RawShm&) = delete;
        RawShm& operator=(const RawShm&) = delete;

        void cleanup();
    };

    /**
     * 创建指定大小的共享内存段
     * @param size 内存大小（字节）
     * @return RawShm 对象
     * @throws std::runtime_error 如果创建失败
     */
    static RawShm create(size_t size);
};

} // namespace anyserve
