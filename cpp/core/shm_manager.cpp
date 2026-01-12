#include "shm_manager.hpp"

#include <fcntl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>
#include <cstring>
#include <random>
#include <sstream>
#include <iomanip>
#include <stdexcept>

namespace anyserve {

ShmManager::RawShm::RawShm(RawShm&& other) noexcept 
    : fd(other.fd), ptr(other.ptr), size(other.size), name(std::move(other.name)) {
    other.fd = -1;
    other.ptr = nullptr;
    other.size = 0;
}

ShmManager::RawShm& ShmManager::RawShm::operator=(RawShm&& other) noexcept {
    if (this != &other) {
        cleanup();
        fd = other.fd;
        ptr = other.ptr;
        size = other.size;
        name = std::move(other.name);
        other.fd = -1;
        other.ptr = nullptr;
        other.size = 0;
    }
    return *this;
}

ShmManager::RawShm::~RawShm() {
    cleanup();
}

void ShmManager::RawShm::cleanup() {
    if (ptr && ptr != MAP_FAILED) {
        munmap(ptr, size);
        ptr = nullptr;
    }
    if (fd >= 0) {
        close(fd);
        fd = -1;
    }
}

ShmManager::RawShm ShmManager::create(size_t size) {
    RawShm shm;
    shm.size = size;
    
    // 生成随机名称（macOS PSHM_NAME_LEN=31 限制）
    std::random_device rd;
    std::mt19937 gen(rd());
    std::uniform_int_distribution<> dis(0, 15);
    std::stringstream ss;
    ss << "/as_";
    for (int i = 0; i < 8; ++i) {
        ss << std::hex << dis(gen);
    }
    shm.name = ss.str();

    // 1. 创建 SHM (O_CREAT | O_RDWR | O_EXCL)
    shm.fd = shm_open(shm.name.c_str(), O_CREAT | O_RDWR | O_EXCL, 0600);
    if (shm.fd < 0) {
        throw std::runtime_error("shm_open failed: " + std::string(strerror(errno)));
    }

    // 2. 立即 unlink（匿名行为）
    shm_unlink(shm.name.c_str());

    // 3. 清除 FD_CLOEXEC，让子进程可以继承
    int flags = fcntl(shm.fd, F_GETFD);
    if (flags >= 0) {
        fcntl(shm.fd, F_SETFD, flags & ~FD_CLOEXEC);
    }

    // 4. 调整大小
    if (ftruncate(shm.fd, static_cast<off_t>(size)) < 0) {
        close(shm.fd);
        throw std::runtime_error("ftruncate failed: " + std::string(strerror(errno)));
    }

    // 5. 内存映射
    shm.ptr = mmap(nullptr, size, PROT_READ | PROT_WRITE, MAP_SHARED, shm.fd, 0);
    if (shm.ptr == MAP_FAILED) {
        close(shm.fd);
        throw std::runtime_error("mmap failed: " + std::string(strerror(errno)));
    }

    return shm;
}

} // namespace anyserve
