import argparse
import json
import os
import sys
import socket
from http.server import BaseHTTPRequestHandler
from socketserver import ThreadingUnixStreamServer
from urllib.parse import urlparse, parse_qs
from multiprocessing import shared_memory

class Request:
    def __init__(self, path, method, headers, body=None):
        self.path = path
        self.method = method
        self.headers = headers
        self.body = body

class App:
    def __init__(self):
        self.routes = {}
        # --- Arena Mode: Pre-attach to the global heavy memory block ---
        self.arena_shm = None
        self.arena_buf = None
        try:
            # Try to attach to the global arena created by Rust
            # Note: We try a few naming conventions for macOS/Linux compat
            names = ["/anyserve-arena-v3", "anyserve-arena-v3"]
            for name in names:
                try:
                    self.arena_shm = shared_memory.SharedMemory(name=name)
                    self.arena_buf = self.arena_shm.buf
                    print(f" -> [Python] Attached to Shared Arena: {name} ({self.arena_shm.size} bytes)")
                    break
                except FileNotFoundError:
                    continue
        except Exception as e:
            print(f" -> [Python] Warning: Could not attach to arena (will use fallback): {e}")

    def route(self, path, method="GET"):
        def decorator(func):
            key = (path, method)
            self.routes[key] = func
            return func
        return decorator

    def _get_handler(self):
        app_instance = self
        
        class RequestHandler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass 

            def do_GET(self):
                self.handle_request("GET")
            
            def do_POST(self):
                self.handle_request("POST")

            def handle_request(self, method):
                path = urlparse(self.path).path
                func = app_instance.routes.get((path, method))
                
                if not func:
                    self.send_error(404, "Not Found")
                    return

                # --- Magic: Optimized Data Path ---
                shm_key = self.headers.get('X-Shm-Key')     # Legacy/Pool Mode
                shm_offset = self.headers.get('X-Shm-Offset') # Arena Mode (Fastest)
                shm_size = self.headers.get('X-Shm-Size')
                
                body = None
                transport_method = "UDS (Standard)"

                try:
                    if shm_offset and shm_size and app_instance.arena_buf:
                        # --- Level 3: Arena Mode (Zero-Syscall) ---
                        offset = int(shm_offset)
                        size = int(shm_size)
                        
                        # Zero-Copy Magic: Create a memoryview directly on the global buffer
                        # This behaves like bytes, but points to existing memory.
                        body = memoryview(app_instance.arena_buf)[offset:offset+size]
                        transport_method = f"ARENA (Offset {offset})"
                        
                    elif shm_key and shm_size:
                        # --- Level 2: Pool/Dynamic Mode (1 Syscall) ---
                        size = int(shm_size)
                        # ... (existing fallback logic if needed) ...
                        candidates = [shm_key]
                        if shm_key.startswith('/'):
                            candidates.append(shm_key[1:])
                        else:
                            candidates.append('/' + shm_key)
                        
                        existing_shm = None
                        for name in candidates:
                            try:
                                existing_shm = shared_memory.SharedMemory(name=name)
                                break
                            except: pass
                        
                        if existing_shm:
                            # Must copy to bytes because we close the shm handle
                            body = bytes(existing_shm.buf[:size])
                            transport_method = f"Dynamic ({shm_key})"
                            existing_shm.close()
                    else:
                        # --- Level 1: Standard UDS (Socket Copy) ---
                        content_length = int(self.headers.get('Content-Length', 0))
                        if content_length > 0:
                            body = self.rfile.read(content_length) # Keep as bytes
                except Exception as e:
                     print(f"Error accessing body: {e}")
                     body = None
                     transport_method = "Error"
                     
                req = Request(self.path, method, self.headers, body)
                
                try:
                    resp_data = func(req)
                    
                    # Helper: Allow returning raw bytes/str directly, or dict
                    if isinstance(resp_data, dict):
                        # Fix for JSON serialization of bytes/memoryview in debug echo
                        if '_meta' not in resp_data:
                             resp_data['_meta'] = {}
                        resp_data['_meta'].update({
                            "worker_pid": os.getpid(),
                            "transport": transport_method
                        })
                        
                        # Custom compact encoder to handle bytes in dict for debugging
                        def default_serializer(o):
                            if isinstance(o, (bytes, memoryview)):
                                return f"<binary data len={len(o)}>"
                            raise TypeError
                            
                        resp_bytes = json.dumps(resp_data, default=default_serializer).encode('utf-8')
                    elif isinstance(resp_data, str):
                         resp_bytes = resp_data.encode('utf-8')
                    elif isinstance(resp_data, bytes):
                        resp_bytes = resp_data
                    else:
                        resp_bytes = b""
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(resp_bytes)
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    self.send_error(500, str(e))

        return RequestHandler

    def run(self, default_sock=None):
        parser = argparse.ArgumentParser()
        parser.add_argument("--socket", type=str, default=default_sock, help="Unix Socket path to bind")
        parser.add_argument("--port", type=int, help="Compatible TCP port")
        args, unknown = parser.parse_known_args()
        
        sock_path = args.socket
        if not sock_path:
            # Fallback to TCP (Dev Mode)
            port = args.port if args.port else 8000
            from http.server import HTTPServer
            print(f" -> [Python App] Dev Mode: Listening on TCP Port {port} ...")
            try:
                httpd = HTTPServer(('127.0.0.1', port), self._get_handler())
                httpd.serve_forever()
            except KeyboardInterrupt:
                pass
            return

        # UDS Mode
        if os.path.exists(sock_path):
            os.remove(sock_path)
            
        print(f" -> [Python App] Prod Mode: Binding to UDS {sock_path} (PID: {os.getpid()})...")
        
        handler_class = self._get_handler()
        
        with ThreadingUnixStreamServer(sock_path, handler_class) as server:
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                if os.path.exists(sock_path):
                    os.remove(sock_path)
