cmake_minimum_required(VERSION 3.15)
project(anyserve_cpp CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

option(BUILD_PYTHON_EXTENSION "Build pybind11 Python extension" ON)
option(BUILD_INGRESS "Build new Dispatcher-based server" ON)

find_package(gRPC CONFIG REQUIRED)
find_package(Protobuf CONFIG REQUIRED)
find_package(nlohmann_json CONFIG REQUIRED)

if(BUILD_PYTHON_EXTENSION)
    find_package(pybind11 CONFIG REQUIRED)
endif()

set(PROTO_SRC_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../proto")
set(GENERATED_DIR "${CMAKE_CURRENT_BINARY_DIR}/generated")
file(MAKE_DIRECTORY ${GENERATED_DIR})

# ============================================================================
# Protobuf: grpc_predict_v2.proto (KServe v2)
# ============================================================================

set(GRPC_PREDICT_PB_SRC "${GENERATED_DIR}/grpc_predict_v2.pb.cc")
set(GRPC_PREDICT_PB_HDR "${GENERATED_DIR}/grpc_predict_v2.pb.h")
set(GRPC_PREDICT_GRPC_SRC "${GENERATED_DIR}/grpc_predict_v2.grpc.pb.cc")
set(GRPC_PREDICT_GRPC_HDR "${GENERATED_DIR}/grpc_predict_v2.grpc.pb.h")

set(PROTOC_EXECUTABLE "${protobuf_PACKAGE_FOLDER_RELEASE}/bin/protoc")
set(GRPC_CPP_PLUGIN "${grpc_PACKAGE_FOLDER_RELEASE}/bin/grpc_cpp_plugin")
message(STATUS "Using protoc: ${PROTOC_EXECUTABLE}")
message(STATUS "Using grpc_cpp_plugin: ${GRPC_CPP_PLUGIN}")

set(GRPC_PREDICT_PROTO "${PROTO_SRC_DIR}/grpc_predict_v2.proto")

add_custom_command(
    OUTPUT ${GRPC_PREDICT_PB_SRC} ${GRPC_PREDICT_PB_HDR} ${GRPC_PREDICT_GRPC_SRC} ${GRPC_PREDICT_GRPC_HDR}
    COMMAND ${PROTOC_EXECUTABLE}
    ARGS --grpc_out=${GENERATED_DIR}
         --cpp_out=${GENERATED_DIR}
         --plugin=protoc-gen-grpc=${GRPC_CPP_PLUGIN}
         -I ${PROTO_SRC_DIR}
         ${GRPC_PREDICT_PROTO}
    DEPENDS ${GRPC_PREDICT_PROTO}
    COMMENT "Generating gRPC C++ code from grpc_predict_v2.proto"
)

# ============================================================================
# Protobuf: worker_management.proto (NEW)
# ============================================================================

set(WORKER_MGMT_PB_SRC "${GENERATED_DIR}/worker_management.pb.cc")
set(WORKER_MGMT_PB_HDR "${GENERATED_DIR}/worker_management.pb.h")
set(WORKER_MGMT_GRPC_SRC "${GENERATED_DIR}/worker_management.grpc.pb.cc")
set(WORKER_MGMT_GRPC_HDR "${GENERATED_DIR}/worker_management.grpc.pb.h")

set(WORKER_MGMT_PROTO "${PROTO_SRC_DIR}/worker_management.proto")

add_custom_command(
    OUTPUT ${WORKER_MGMT_PB_SRC} ${WORKER_MGMT_PB_HDR} ${WORKER_MGMT_GRPC_SRC} ${WORKER_MGMT_GRPC_HDR}
    COMMAND ${PROTOC_EXECUTABLE}
    ARGS --grpc_out=${GENERATED_DIR}
         --cpp_out=${GENERATED_DIR}
         --plugin=protoc-gen-grpc=${GRPC_CPP_PLUGIN}
         -I ${PROTO_SRC_DIR}
         ${WORKER_MGMT_PROTO}
    DEPENDS ${WORKER_MGMT_PROTO}
    COMMENT "Generating gRPC C++ code from worker_management.proto"
)

# ============================================================================
# Core Library (Legacy - for Python extension)
# ============================================================================

add_library(anyserve_core_lib STATIC
    core/shm_manager.cpp
    server/process_supervisor.cpp
    server/anyserve_core.cpp
    ${GRPC_PREDICT_PB_SRC}
    ${GRPC_PREDICT_GRPC_SRC}
)

target_include_directories(anyserve_core_lib PUBLIC
    core
    server
    ${GENERATED_DIR}
)

target_link_libraries(anyserve_core_lib PUBLIC
    gRPC::grpc++
    gRPC::grpc++_reflection
    protobuf::libprotobuf
    nlohmann_json::nlohmann_json
)

# ============================================================================
# Dispatcher Library (NEW)
# ============================================================================

if(BUILD_INGRESS)
    add_library(anyserve_dispatcher_lib STATIC
        server/model_registry.cpp
        server/worker_client.cpp
        server/anyserve_dispatcher.cpp
        ${GRPC_PREDICT_PB_SRC}
        ${GRPC_PREDICT_GRPC_SRC}
        ${WORKER_MGMT_PB_SRC}
        ${WORKER_MGMT_GRPC_SRC}
    )

    target_include_directories(anyserve_dispatcher_lib PUBLIC
        server
        ${GENERATED_DIR}
    )

    target_link_libraries(anyserve_dispatcher_lib PUBLIC
        gRPC::grpc++
        gRPC::grpc++_reflection
        protobuf::libprotobuf
    )
endif()

# ============================================================================
# Executables
# ============================================================================

# Legacy node (old architecture)
add_executable(anyserve_node
    server/main.cpp
)

target_link_libraries(anyserve_node PRIVATE
    anyserve_core_lib
)

# Dispatcher node (new architecture)
if(BUILD_INGRESS)
    add_executable(anyserve_dispatcher
        server/main_v2.cpp
    )

    target_link_libraries(anyserve_dispatcher PRIVATE
        anyserve_dispatcher_lib
    )

    # Install
    install(TARGETS anyserve_dispatcher RUNTIME DESTINATION bin)
endif()

# ============================================================================
# Python Extension (Optional)
# ============================================================================

if(BUILD_PYTHON_EXTENSION)
    pybind11_add_module(_core extension/python_bindings.cpp)
    target_link_libraries(_core PRIVATE anyserve_core_lib)
    install(TARGETS _core LIBRARY DESTINATION anyserve)
endif()
