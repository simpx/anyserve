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
from pathlib import Path
from typing import List, Optional


def main():
    parser = argparse.ArgumentParser(
        description='AnyServe Server - KServe v2 Model Serving',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  anyserve examples.kserve_server:app
  anyserve examples.kserve_server:app --port 8080 --workers 4
  anyserve examples.kserve_server:app --reload
        """
    )
    parser.add_argument('app', help='Application module (e.g., examples.kserve_server:app)')
    parser.add_argument('--host', default='0.0.0.0', help='Bind host (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=8000, help='Bind port (default: 8000)')
    parser.add_argument('--workers', type=int, default=1, help='Number of workers (default: 1)')
    parser.add_argument('--reload', action='store_true', help='Auto-reload on code changes (not implemented yet)')
    parser.add_argument('--ingress-bin', default=None, help='Path to anyserve_ingress binary (auto-detect if not specified)')

    args = parser.parse_args()

    # Create server instance
    server = AnyServeServer(
        app=args.app,
        host=args.host,
        port=args.port,
        workers=args.workers,
        reload=args.reload,
        ingress_bin=args.ingress_bin
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
        ingress_bin: Optional[str] = None
    ):
        self.app = app
        self.host = host
        self.port = port
        self.workers = workers
        self.reload = reload
        self.ingress_bin = ingress_bin or self._find_ingress_binary()

        self.management_port = port + 1000  # e.g., 9000 for port 8000

        self.ingress_proc: Optional[subprocess.Popen] = None
        self.worker_procs: List[subprocess.Popen] = []

        self.running = False

        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.running = False

    def _find_ingress_binary(self) -> str:
        """查找 anyserve_ingress 可执行文件"""
        # Try multiple locations
        candidates = [
            # Relative to current directory
            "./cpp/build/anyserve_ingress",
            "./build/anyserve_ingress",
            # Relative to package installation
            str(Path(__file__).parent.parent.parent / "cpp" / "build" / "anyserve_ingress"),
            # In PATH
            "anyserve_ingress",
        ]

        for path in candidates:
            if path == "anyserve_ingress":
                # Check if it's in PATH
                import shutil
                if shutil.which(path):
                    return path
            elif os.path.exists(path) and os.access(path, os.X_OK):
                return os.path.abspath(path)

        raise FileNotFoundError(
            "anyserve_ingress binary not found. Please:\n"
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

    def start(self):
        """启动服务器"""
        self.running = True

        print("[AnyServe] Starting AnyServe Server...")
        print(f"[AnyServe] Application: {self.app}")
        print(f"[AnyServe] KServe gRPC port: {self.port}")
        print(f"[AnyServe] Management port: {self.management_port}")
        print(f"[AnyServe] Workers: {self.workers}")
        print()

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

        # 5. 打印启动信息
        print()
        print("=" * 60)
        print(f"[AnyServe] Server started successfully!")
        print(f"[AnyServe] gRPC endpoint: {self.host}:{self.port}")
        print(f"[AnyServe] Workers: {self.workers}")
        print(f"[AnyServe] Press Ctrl+C to stop")
        print("=" * 60)
        print()

        # 6. 主循环 - 监控进程
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
        for i in range(self.workers):
            worker_id = f"worker-{i}"
            print(f"[AnyServe] Starting Worker {i+1}/{self.workers} (id={worker_id})")

            cmd = [
                sys.executable,
                "-m", "anyserve.worker",
                "--app", self.app,
                "--ingress", f"localhost:{self.management_port}",
                "--worker-id", worker_id,
            ]

            worker_proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
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
