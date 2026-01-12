cmake_minimum_required(VERSION 3.15)
project(anyserve_cpp CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# Option to build Python extension
option(BUILD_PYTHON_EXTENSION "Build pybind11 Python extension" ON)

# Dependencies provided by Conan
find_package(gRPC CONFIG REQUIRED)
find_package(Protobuf CONFIG REQUIRED)
find_package(nlohmann_json CONFIG REQUIRED)

if(BUILD_PYTHON_EXTENSION)
    find_package(pybind11 CONFIG REQUIRED)
endif()

# Proto files - generate in build directory
set(PROTO_SRC_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../proto")
set(GENERATED_DIR "${CMAKE_CURRENT_BINARY_DIR}/generated")

# Ensure generated directory exists
file(MAKE_DIRECTORY ${GENERATED_DIR})

set(GRPC_PREDICT_PB_SRC "${GENERATED_DIR}/grpc_predict_v2.pb.cc")
set(GRPC_PREDICT_PB_HDR "${GENERATED_DIR}/grpc_predict_v2.pb.h")
set(GRPC_PREDICT_GRPC_SRC "${GENERATED_DIR}/grpc_predict_v2.grpc.pb.cc")
set(GRPC_PREDICT_GRPC_HDR "${GENERATED_DIR}/grpc_predict_v2.grpc.pb.h")

# Always generate proto files using Conan's protoc (must match libprotobuf version)
get_target_property(gRPC_CPP_PLUGIN_EXECUTABLE gRPC::grpc_cpp_plugin IMPORTED_LOCATION_RELEASE)
if(NOT gRPC_CPP_PLUGIN_EXECUTABLE)
    get_target_property(gRPC_CPP_PLUGIN_EXECUTABLE gRPC::grpc_cpp_plugin IMPORTED_LOCATION)
endif()

# Get protoc from Conan's protobuf package (protobuf_PACKAGE_FOLDER_RELEASE is set by CMakeDeps)
# This ensures we use the protoc that matches the libprotobuf version
if(protobuf_PACKAGE_FOLDER_RELEASE)
    set(PROTOC_EXECUTABLE "${protobuf_PACKAGE_FOLDER_RELEASE}/bin/protoc")
elseif(TARGET protobuf::protoc)
    get_target_property(PROTOC_EXECUTABLE protobuf::protoc IMPORTED_LOCATION_RELEASE)
    if(NOT PROTOC_EXECUTABLE)
        get_target_property(PROTOC_EXECUTABLE protobuf::protoc IMPORTED_LOCATION)
    endif()
else()
    message(FATAL_ERROR "Could not find protoc executable. Make sure Conan dependencies are installed.")
endif()
message(STATUS "Using protoc: ${PROTOC_EXECUTABLE}")

set(GRPC_PREDICT_PROTO "${PROTO_SRC_DIR}/grpc_predict_v2.proto")

add_custom_command(
    OUTPUT ${GRPC_PREDICT_PB_SRC} ${GRPC_PREDICT_PB_HDR} ${GRPC_PREDICT_GRPC_SRC} ${GRPC_PREDICT_GRPC_HDR}
    COMMAND ${PROTOC_EXECUTABLE}
    ARGS --grpc_out=${GENERATED_DIR}
         --cpp_out=${GENERATED_DIR}
         --plugin=protoc-gen-grpc=${gRPC_CPP_PLUGIN_EXECUTABLE}
         -I ${PROTO_SRC_DIR}
         ${GRPC_PREDICT_PROTO}
    DEPENDS ${GRPC_PREDICT_PROTO}
    COMMENT "Generating gRPC C++ code from grpc_predict_v2.proto"
)

# Core library (static, used by both executable and Python extension)
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

# Standalone executable
add_executable(anyserve_node
    server/main.cpp
)

target_link_libraries(anyserve_node PRIVATE
    anyserve_core_lib
)

# Python extension (pybind11)
if(BUILD_PYTHON_EXTENSION)
    pybind11_add_module(_core
        extension/python_bindings.cpp
    )
    
    target_link_libraries(_core PRIVATE
        anyserve_core_lib
    )
    
    # Install to python package directory (for scikit-build-core)
    install(TARGETS _core
        LIBRARY DESTINATION anyserve
    )
endif()
