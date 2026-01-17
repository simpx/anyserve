"""
AnyServe run command - Run a custom AnyServe application.

Usage:
    anyserve run examples.basic.app:app --port 8000 --workers 1
"""

import sys
import os
import subprocess
import time
import signal
import threading
import importlib
import uuid
from pathlib import Path
from typing import List, Optional

import click
import requests


@click.command()
@click.argument("app", required=True)
@click.option("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
@click.option("--port", type=int, default=8000, help="Bind port (default: 8000)")
@click.option("--workers", type=int, default=1, help="Number of workers (default: 1)")
@click.option("--reload", is_flag=True, help="Auto-reload on code changes (not implemented)")
@click.option("--agent-bin", default=None, help="Path to anyserve_agent binary")
@click.option("--api-server", default=None, help="API Server URL for capability registration")
@click.option("--object-store", default="/tmp/anyserve-objects", help="Object store path")
@click.option("--replica-id", default=None, help="Replica ID for API Server registration")
@click.option("--factory", is_flag=True, help="Treat app as factory function")
def run_command(app, host, port, workers, reload, agent_bin, api_server, object_store, replica_id, factory):
    """Run an AnyServe application.

    Example:
        anyserve run examples.basic.app:app --port 8000 --workers 1
    """
    # Force unbuffered stdout
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(line_buffering=True)

    # Generate replica ID if not provided
    if replica_id is None:
        replica_id = f"replica-{port}-{str(uuid.uuid4())[:8]}"

    server = AnyServeServer(
        app=app,
        host=host,
        port=port,
        workers=workers,
        reload=reload,
        agent_bin=agent_bin,
        api_server=api_server,
        object_store=object_store,
        replica_id=replica_id,
        factory=factory,
    )

    try:
        server.start()
    except KeyboardInterrupt:
        click.echo("\n[AnyServe] Received Ctrl+C, shutting down...")
    except Exception as e:
        click.echo(f"[AnyServe] Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        server.stop()


class AnyServeServer:
    """AnyServe server manager for running custom applications."""

    def __init__(
        self,
        app: str,
        host: str = "0.0.0.0",
        port: int = 8000,
        workers: int = 1,
        reload: bool = False,
        agent_bin: Optional[str] = None,
        api_server: Optional[str] = None,
        object_store: str = "/tmp/anyserve-objects",
        replica_id: Optional[str] = None,
        factory: bool = False,
    ):
        self.app = app
        self.host = host
        self.port = port
        self.workers = workers
        self.reload = reload
        self.agent_bin = agent_bin or self._find_agent()
        self.api_server = api_server
        self.object_store = object_store
        self.replica_id = replica_id
        self.factory = factory

        self.management_port = port + 1000

        self.ingress_proc: Optional[subprocess.Popen] = None
        self.worker_procs: List[subprocess.Popen] = []

        self.running = False
        self.keepalive_thread: Optional[threading.Thread] = None
        self.capabilities: List[dict] = []

        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        self.running = False

    def _find_agent(self) -> str:
        """Find anyserve_agent executable."""
        import shutil

        # 1. Check package's scripts directory (wheel installation)
        if hasattr(sys, 'prefix'):
            pkg_bin = Path(sys.prefix) / "bin" / "anyserve_agent"
            if pkg_bin.is_file() and os.access(str(pkg_bin), os.X_OK):
                return str(pkg_bin)

        # 2. Check PATH
        agent = shutil.which("anyserve_agent")
        if agent:
            return agent

        # 3. Development paths
        candidates = [
            "./cpp/build/anyserve_agent",
            "./build/anyserve_agent",
            str(Path(__file__).parent.parent.parent.parent / "cpp" / "build" / "anyserve_agent"),
        ]

        for path in candidates:
            if os.path.exists(path) and os.access(path, os.X_OK):
                return os.path.abspath(path)

        raise FileNotFoundError(
            "anyserve_agent binary not found. Please:\n"
            "  1. Install anyserve: pip install anyserve\n"
            "  2. Or compile C++ code: cd cpp && mkdir -p build && cd build && "
            "conan install .. --build=missing && cmake .. && cmake --build .\n"
            "  3. Or specify the path with --agent-bin"
        )

    def _wait_for_port(self, host: str, port: int, timeout: int = 10) -> bool:
        """Wait for a port to become available."""
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
        """Load app module and get capabilities."""
        try:
            module_path, app_name = self.app.rsplit(":", 1)
            module = importlib.import_module(module_path)

            if self.factory:
                # Factory mode: call function to get app (for capability discovery only)
                # Note: In main process, we just try to get capabilities if possible
                # The actual app creation happens in worker processes
                factory_func = getattr(module, app_name, None)
                if factory_func is None:
                    print(f"[AnyServe] Warning: Could not find factory '{app_name}' in '{module_path}'")
                    return
                # Skip calling factory in main process - capabilities will be discovered by workers
                print(f"[AnyServe] Factory mode: capabilities will be loaded by workers")
                return
            else:
                app_obj = getattr(module, app_name, None)

            if app_obj is None:
                print(f"[AnyServe] Warning: Could not find '{app_name}' in '{module_path}'")
                return

            if hasattr(app_obj, 'get_capabilities'):
                self.capabilities = app_obj.get_capabilities()
                print(f"[AnyServe] Loaded {len(self.capabilities)} capabilities from app")
            else:
                print(f"[AnyServe] Warning: App has no get_capabilities() method")

        except Exception as e:
            print(f"[AnyServe] Warning: Failed to load capabilities: {e}")

    def _register_to_api_server(self):
        """Register with API Server via SSE long connection."""
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
                        reconnect_delay = 1

                        for line in resp.iter_lines():
                            if not self.running:
                                break
                            if line:
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
                        reconnect_delay = min(reconnect_delay * 2, 30)

        self.keepalive_thread = threading.Thread(target=register_loop, daemon=True)
        self.keepalive_thread.start()
        print("[AnyServe] API Server connection thread started")

    def start(self):
        """Start the server."""
        self.running = True

        print("[AnyServe] Starting AnyServe Server...")
        print(f"[AnyServe] Application: {self.app}")
        print(f"[AnyServe] KServe gRPC port: {self.port}")
        print(f"[AnyServe] Management port: {self.management_port}")
        print(f"[AnyServe] Workers: {self.workers}")
        if self.api_server:
            print(f"[AnyServe] API Server: {self.api_server}")
        print()

        self._load_app_capabilities()
        self._start_ingress()

        print(f"[AnyServe] Waiting for Ingress to start...")
        if not self._wait_for_port("localhost", self.management_port, timeout=10):
            raise RuntimeError("Ingress failed to start within timeout")

        print(f"[AnyServe] Ingress started successfully")

        self._start_workers()
        time.sleep(1)

        if self.api_server:
            self._register_to_api_server()

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

        self._monitor_processes()

    def _start_ingress(self):
        """Start C++ Agent process."""
        print(f"[AnyServe] Starting C++ Agent: {self.agent_bin}")

        cmd = [
            self.agent_bin,
            "--port", str(self.port),
            "--management-port", str(self.management_port),
        ]

        self.ingress_proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        def read_ingress_output():
            if self.ingress_proc and self.ingress_proc.stdout:
                for line in self.ingress_proc.stdout:
                    print(f"[Ingress] {line.rstrip()}")

        threading.Thread(target=read_ingress_output, daemon=True).start()

    def _start_workers(self):
        """Start Python Worker processes."""
        env = os.environ.copy()
        env['PYTHONUNBUFFERED'] = '1'

        for i in range(self.workers):
            worker_id = f"worker-{self.port}-{i}"
            print(f"[AnyServe] Starting Worker {i+1}/{self.workers} (id={worker_id})")

            cmd = [
                sys.executable,
                "-m", "anyserve.worker",
                "--app", self.app,
                "--ingress", f"localhost:{self.management_port}",
                "--worker-id", worker_id,
                "--object-store", self.object_store,
                "--grpc-port", str(self.port + 100),  # Streaming gRPC port
            ]

            if self.factory:
                cmd.append("--factory")

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

            def read_worker_output(proc, wid):
                if proc.stdout:
                    for line in proc.stdout:
                        print(f"[{wid}] {line.rstrip()}")

            threading.Thread(target=read_worker_output, args=(worker_proc, worker_id), daemon=True).start()
            time.sleep(0.2)

    def _monitor_processes(self):
        """Monitor child processes."""
        try:
            while self.running:
                time.sleep(1)

                if self.ingress_proc and self.ingress_proc.poll() is not None:
                    print("[AnyServe] ERROR: Ingress process crashed!")
                    self.running = False
                    break

                for i, proc in enumerate(self.worker_procs):
                    if proc.poll() is not None:
                        print(f"[AnyServe] WARNING: Worker {i} crashed!")

        except KeyboardInterrupt:
            pass

    def stop(self):
        """Stop the server."""
        if not self.ingress_proc and not self.worker_procs:
            return

        print("\n[AnyServe] Shutting down...")

        if self.keepalive_thread:
            print("[AnyServe] Stopping keepalive connection...")

        for i, proc in enumerate(self.worker_procs):
            try:
                print(f"[AnyServe] Stopping Worker {i}...")
                proc.terminate()
            except Exception as e:
                print(f"[AnyServe] Error stopping worker {i}: {e}")

        for i, proc in enumerate(self.worker_procs):
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print(f"[AnyServe] Force killing Worker {i}")
                proc.kill()

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
