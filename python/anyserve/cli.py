#!/usr/bin/env python3
"""
AnyServe CLI - 类似 uvicorn 的启动器

Usage:
    anyserve app:app
    anyserve app:app --port 8080 --workers 4
    anyserve app:app --reload
"""

import sys
import os
import subprocess
import time
import signal
import argparse
import threading
import importlib
from pathlib import Path
from typing import List, Optional

import requests


def main():
    # Force unbuffered stdout for real-time log output
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(line_buffering=True)

    parser = argparse.ArgumentParser(
        description='AnyServe Server - KServe v2 Model Serving',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  anyserve examples.kserve_server:app
  anyserve examples.kserve_server:app --port 8080 --workers 4
  anyserve examples.kserve_server:app --reload

MVP Examples:
  anyserve examples.chat_app:app --port 50051 --api-server http://localhost:8080
  anyserve examples.embed_app:app --port 50052 --api-server http://localhost:8080
        """
    )
    parser.add_argument('app', help='Application module (e.g., examples.kserve_server:app)')
    parser.add_argument('--host', default='0.0.0.0', help='Bind host (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=8000, help='Bind port (default: 8000)')
    parser.add_argument('--workers', type=int, default=1, help='Number of workers (default: 1)')
    parser.add_argument('--reload', action='store_true', help='Auto-reload on code changes (not implemented yet)')
    parser.add_argument('--ingress-bin', default=None, help='Path to anyserve_dispatcher binary (auto-detect if not specified)')
    # MVP options
    parser.add_argument('--api-server', default=None, help='API Server URL for capability registration (e.g., http://localhost:8080)')
    parser.add_argument('--object-store', default='/tmp/anyserve-objects', help='Object store path (default: /tmp/anyserve-objects)')
    parser.add_argument('--replica-id', default=None, help='Replica ID for API Server registration (auto-generated if not specified)')

    args = parser.parse_args()

    # Generate replica ID if not provided
    replica_id = args.replica_id
    if replica_id is None:
        import uuid
        replica_id = f"replica-{args.port}-{str(uuid.uuid4())[:8]}"

    # Create server instance
    server = AnyServeServer(
        app=args.app,
        host=args.host,
        port=args.port,
        workers=args.workers,
        reload=args.reload,
        ingress_bin=args.ingress_bin,
        api_server=args.api_server,
        object_store=args.object_store,
        replica_id=replica_id,
    )

    # Start server
    try:
        server.start()
    except KeyboardInterrupt:
        print("\n[AnyServe] Received Ctrl+C, shutting down...")
    except Exception as e:
        print(f"[AnyServe] Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        server.stop()


class AnyServeServer:
    """AnyServe 服务器管理器"""

    def __init__(
        self,
        app: str,
        host: str = "0.0.0.0",
        port: int = 8000,
        workers: int = 1,
        reload: bool = False,
        ingress_bin: Optional[str] = None,
        api_server: Optional[str] = None,
        object_store: str = "/tmp/anyserve-objects",
        replica_id: Optional[str] = None,
    ):
        self.app = app
        self.host = host
        self.port = port
        self.workers = workers
        self.reload = reload
        self.ingress_bin = ingress_bin or self._find_ingress_binary()
        self.api_server = api_server
        self.object_store = object_store
        self.replica_id = replica_id

        self.management_port = port + 1000  # e.g., 9000 for port 8000

        self.ingress_proc: Optional[subprocess.Popen] = None
        self.worker_procs: List[subprocess.Popen] = []

        self.running = False
        self.keepalive_thread: Optional[threading.Thread] = None
        self.capabilities: List[dict] = []  # Loaded from app

        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.running = False

    def _find_ingress_binary(self) -> str:
        """查找 anyserve_dispatcher 可执行文件"""
        # Try multiple locations
        candidates = [
            # Relative to current directory
            "./cpp/build/anyserve_dispatcher",
            "./build/anyserve_dispatcher",
            # Relative to package installation
            str(Path(__file__).parent.parent.parent / "cpp" / "build" / "anyserve_dispatcher"),
            # In PATH
            "anyserve_dispatcher",
        ]

        for path in candidates:
            if path == "anyserve_dispatcher":
                # Check if it's in PATH
                import shutil
                if shutil.which(path):
                    return path
            elif os.path.exists(path) and os.access(path, os.X_OK):
                return os.path.abspath(path)

        raise FileNotFoundError(
            "anyserve_dispatcher binary not found. Please:\n"
            "  1. Compile C++ code: cd cpp && mkdir -p build && cd build && "
            "conan install .. --build=missing && cmake .. -DCMAKE_TOOLCHAIN_FILE=../conan_toolchain.cmake && "
            "cmake --build .\n"
            "  2. Or specify the path with --ingress-bin"
        )

    def _wait_for_port(self, host: str, port: int, timeout: int = 10) -> bool:
        """等待端口可用"""
        import socket
        start = time.time()

        while time.time() - start < timeout:
            try:
                sock = socket.socket()
                sock.settimeout(1)
                sock.connect((host, port))
                sock.close()
                return True
            except (socket.error, socket.timeout):
                time.sleep(0.5)

        return False

    def _load_app_capabilities(self):
        """加载 app 模块并获取 capabilities"""
        try:
            module_path, app_name = self.app.rsplit(":", 1)

            # Import the module
            module = importlib.import_module(module_path)

            # Get the app object
            app_obj = getattr(module, app_name, None)
            if app_obj is None:
                print(f"[AnyServe] Warning: Could not find '{app_name}' in '{module_path}'")
                return

            # Get capabilities from the app
            if hasattr(app_obj, 'get_capabilities'):
                self.capabilities = app_obj.get_capabilities()
                print(f"[AnyServe] Loaded {len(self.capabilities)} capabilities from app")
            else:
                print(f"[AnyServe] Warning: App has no get_capabilities() method")

        except Exception as e:
            print(f"[AnyServe] Warning: Failed to load capabilities: {e}")
            # Don't fail, just continue with empty capabilities

    def _register_to_api_server(self):
        """POST /register 到 API Server (SSE 长连接，自动保活)"""
        if not self.api_server:
            return

        endpoint = f"{self.host}:{self.port}"
        if self.host == "0.0.0.0":
            endpoint = f"localhost:{self.port}"

        payload = {
            "replica_id": self.replica_id,
            "endpoint": endpoint,
            "capabilities": self.capabilities,
        }

        def register_loop():
            url = f"{self.api_server}/register"
            reconnect_delay = 1

            while self.running:
                try:
                    print(f"[AnyServe] Connecting to API Server: {url}")
                    with requests.post(url, json=payload, stream=True, timeout=(10, None)) as resp:
                        resp.raise_for_status()
                        reconnect_delay = 1  # Reset on successful connection

                        for line in resp.iter_lines():
                            if not self.running:
                                break
                            if line:
                                # Parse SSE data line
                                if line.startswith(b"data: "):
                                    data = line[6:].decode()
                                    msg = __import__("json").loads(data)
                                    if msg.get("status") == "registered":
                                        print(f"[AnyServe] Registered to API Server: {msg}")

                except requests.RequestException as e:
                    if self.running:
                        print(f"[AnyServe] API Server connection lost: {e}")
                        print(f"[AnyServe] Reconnecting in {reconnect_delay}s...")
                        time.sleep(reconnect_delay)
                        reconnect_delay = min(reconnect_delay * 2, 30)  # Exponential backoff

        self.keepalive_thread = threading.Thread(target=register_loop, daemon=True)
        self.keepalive_thread.start()
        print("[AnyServe] API Server connection thread started")

    def start(self):
        """启动服务器"""
        self.running = True

        print("[AnyServe] Starting AnyServe Server...")
        print(f"[AnyServe] Application: {self.app}")
        print(f"[AnyServe] KServe gRPC port: {self.port}")
        print(f"[AnyServe] Management port: {self.management_port}")
        print(f"[AnyServe] Workers: {self.workers}")
        if self.api_server:
            print(f"[AnyServe] API Server: {self.api_server}")
        print()

        # 0. 加载 app，获取 capabilities
        self._load_app_capabilities()

        # 1. 启动 C++ Ingress
        self._start_ingress()

        # 2. 等待 Ingress 就绪
        print(f"[AnyServe] Waiting for Ingress to start...")
        if not self._wait_for_port("localhost", self.management_port, timeout=10):
            raise RuntimeError("Ingress failed to start within timeout")

        print(f"[AnyServe] Ingress started successfully")

        # 3. 启动 Workers
        self._start_workers()

        # 4. 等待 Workers 注册
        time.sleep(1)

        # 5. 注册到 API Server (如果配置了，SSE 长连接)
        if self.api_server:
            self._register_to_api_server()

        # 6. 打印启动信息
        print()
        print("=" * 60)
        print(f"[AnyServe] Server started successfully!")
        print(f"[AnyServe] gRPC endpoint: {self.host}:{self.port}")
        print(f"[AnyServe] Workers: {self.workers}")
        if self.api_server:
            print(f"[AnyServe] Registered to API Server: {self.api_server}")
            print(f"[AnyServe] Replica ID: {self.replica_id}")
            print(f"[AnyServe] Capabilities: {self.capabilities}")
        print(f"[AnyServe] Press Ctrl+C to stop")
        print("=" * 60)
        print()

        # 7. 主循环 - 监控进程
        self._monitor_processes()

    def _start_ingress(self):
        """启动 C++ Ingress 进程"""
        print(f"[AnyServe] Starting C++ Ingress: {self.ingress_bin}")

        cmd = [
            self.ingress_bin,
            "--port", str(self.port),
            "--management-port", str(self.management_port),
        ]

        self.ingress_proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1  # Line buffered
        )

        # Start a thread to read and print ingress output
        import threading
        def read_ingress_output():
            if self.ingress_proc and self.ingress_proc.stdout:
                for line in self.ingress_proc.stdout:
                    print(f"[Ingress] {line.rstrip()}")

        threading.Thread(target=read_ingress_output, daemon=True).start()

    def _start_workers(self):
        """启动 Python Worker 进程"""
        # Set unbuffered output for worker subprocesses
        env = os.environ.copy()
        env['PYTHONUNBUFFERED'] = '1'

        for i in range(self.workers):
            worker_id = f"worker-{i}"
            print(f"[AnyServe] Starting Worker {i+1}/{self.workers} (id={worker_id})")

            cmd = [
                sys.executable,
                "-m", "anyserve.worker",
                "--app", self.app,
                "--ingress", f"localhost:{self.management_port}",
                "--worker-id", worker_id,
                "--object-store", self.object_store,
            ]

            # Add MVP options if configured
            if self.api_server:
                cmd.extend(["--api-server", self.api_server])
            if self.replica_id:
                cmd.extend(["--replica-id", self.replica_id])

            worker_proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env
            )
            self.worker_procs.append(worker_proc)

            # Start a thread to read and print worker output
            import threading
            def read_worker_output(proc, wid):
                if proc.stdout:
                    for line in proc.stdout:
                        print(f"[{wid}] {line.rstrip()}")

            threading.Thread(target=read_worker_output, args=(worker_proc, worker_id), daemon=True).start()

            # Small delay between workers
            time.sleep(0.2)

    def _monitor_processes(self):
        """监控子进程"""
        try:
            while self.running:
                time.sleep(1)

                # Check if ingress crashed
                if self.ingress_proc and self.ingress_proc.poll() is not None:
                    print("[AnyServe] ERROR: Ingress process crashed!")
                    self.running = False
                    break

                # Check if any worker crashed
                for i, proc in enumerate(self.worker_procs):
                    if proc.poll() is not None:
                        print(f"[AnyServe] WARNING: Worker {i} crashed!")
                        # Could implement restart logic here

        except KeyboardInterrupt:
            pass

    def stop(self):
        """停止服务器"""
        if not self.ingress_proc and not self.worker_procs:
            return

        print("\n[AnyServe] Shutting down...")

        # 0. Stop keepalive (daemon thread will exit when self.running = False)
        if self.keepalive_thread:
            print("[AnyServe] Stopping keepalive connection...")

        # 1. Stop workers first
        for i, proc in enumerate(self.worker_procs):
            try:
                print(f"[AnyServe] Stopping Worker {i}...")
                proc.terminate()
            except Exception as e:
                print(f"[AnyServe] Error stopping worker {i}: {e}")

        # 2. Wait for workers to exit (with timeout)
        for i, proc in enumerate(self.worker_procs):
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print(f"[AnyServe] Force killing Worker {i}")
                proc.kill()

        # 3. Stop ingress
        if self.ingress_proc:
            try:
                print("[AnyServe] Stopping Ingress...")
                self.ingress_proc.terminate()
                self.ingress_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print("[AnyServe] Force killing Ingress")
                self.ingress_proc.kill()

        print("[AnyServe] All processes stopped")
        print("[AnyServe] Goodbye!")


if __name__ == "__main__":
    main()
