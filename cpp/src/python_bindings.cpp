/**
 * python_bindings.cpp - pybind11 绑定
 * 
 * 将 C++ AnyserveCore 暴露为 Python 模块 anyserve._core
 */

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/functional.h>

#include "anyserve_core.hpp"

namespace py = pybind11;

namespace anyserve {

/**
 * Python 兼容的 AnyserveCore 包装器
 * 
 * 处理：
 * 1. Python dispatcher 回调（GIL 管理）
 * 2. bytes <-> std::string 转换
 */
class PyAnyserveCore {
public:
    PyAnyserveCore(const std::string& root_dir,
                   const std::string& instance_id,
                   int port,
                   py::object dispatcher)
        : core_(root_dir, instance_id, port), py_dispatcher_(std::move(dispatcher)) {
        
        // 设置 dispatcher 回调
        if (!py_dispatcher_.is_none()) {
            core_.set_dispatcher([this](const std::string& capability,
                                        const std::string& args_pickle,
                                        bool is_delegated) -> std::string {
                // 获取 GIL
                py::gil_scoped_acquire acquire;
                
                try {
                    // 调用 Python dispatcher.dispatch(capability, args_pickle, is_delegated)
                    py::bytes args_bytes(args_pickle);
                    py::object result = py_dispatcher_.attr("dispatch")(
                        capability, args_bytes, is_delegated
                    );
                    
                    // 转换结果为 bytes
                    if (py::isinstance<py::bytes>(result)) {
                        return std::string(py::cast<std::string>(result));
                    } else {
                        return "";
                    }
                } catch (const py::error_already_set& e) {
                    throw std::runtime_error(std::string("Python dispatch error: ") + e.what());
                }
            });
        }
        
        // 自动启动服务
        core_.start();
    }
    
    ~PyAnyserveCore() {
        // 停止时需要释放 GIL
        py::gil_scoped_release release;
        core_.stop();
    }
    
    void register_capability(const std::string& name) {
        py::gil_scoped_release release;
        core_.register_capability(name);
    }
    
    py::list lookup_capability(const std::string& name) {
        std::vector<std::string> endpoints;
        {
            py::gil_scoped_release release;
            endpoints = core_.lookup_capability(name);
        }
        
        py::list result;
        for (const auto& ep : endpoints) {
            result.append(ep);
        }
        return result;
    }
    
    py::bytes remote_call(const std::string& address,
                          const std::string& capability,
                          py::bytes args_pickle,
                          bool is_delegated) {
        std::string args_str = py::cast<std::string>(args_pickle);
        std::string result;
        
        {
            py::gil_scoped_release release;
            result = core_.remote_call(address, capability, args_str, is_delegated);
        }
        
        return py::bytes(result);
    }
    
    std::string get_address() const {
        return core_.get_address();
    }
    
    std::string instance_id() const {
        return core_.instance_id();
    }
    
    int port() const {
        return core_.port();
    }
    
    bool is_running() const {
        return core_.is_running();
    }
    
    void stop() {
        py::gil_scoped_release release;
        core_.stop();
    }

private:
    AnyserveCore core_;
    py::object py_dispatcher_;
};

} // namespace anyserve

PYBIND11_MODULE(_core, m) {
    m.doc() = "AnyServe C++ Core - Capability-Oriented Serving Runtime";
    
    py::class_<anyserve::PyAnyserveCore>(m, "AnyserveCore")
        .def(py::init<const std::string&, const std::string&, int, py::object>(),
             py::arg("root_dir"),
             py::arg("instance_id"),
             py::arg("port"),
             py::arg("dispatcher"),
             R"doc(
             创建 AnyserveCore 实例
             
             Args:
                 root_dir: 根目录（用于存储状态、服务发现）
                 instance_id: 实例唯一标识
                 port: gRPC 服务端口（0 = 随机分配）
                 dispatcher: Python dispatcher 对象，需要有 dispatch(capability, args_pickle, is_delegated) 方法
             )doc")
        .def("register_capability", &anyserve::PyAnyserveCore::register_capability,
             py::arg("name"),
             "注册本地 capability")
        .def("lookup_capability", &anyserve::PyAnyserveCore::lookup_capability,
             py::arg("name"),
             "查找提供指定 capability 的端点列表")
        .def("remote_call", &anyserve::PyAnyserveCore::remote_call,
             py::arg("address"),
             py::arg("capability"),
             py::arg("args_pickle"),
             py::arg("is_delegated"),
             "远程调用指定地址的 capability")
        .def("get_address", &anyserve::PyAnyserveCore::get_address,
             "获取本实例的地址")
        .def_property_readonly("instance_id", &anyserve::PyAnyserveCore::instance_id,
             "实例 ID")
        .def_property_readonly("port", &anyserve::PyAnyserveCore::port,
             "gRPC 服务端口")
        .def_property_readonly("is_running", &anyserve::PyAnyserveCore::is_running,
             "是否正在运行")
        .def("stop", &anyserve::PyAnyserveCore::stop,
             "停止服务");
    
    m.attr("__version__") = "0.1.0";
}
