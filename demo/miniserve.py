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

                # --- Magic: Check for Shared Memory Headers ---
                shm_key = self.headers.get('X-Shm-Key')
                shm_size = self.headers.get('X-Shm-Size')
                
                body = None
                transport_method = "UDS (Standard)"

                if shm_key and shm_size:
                    # Case 1: Data via Shared Memory (Zero-ish Copy reading)
                    try:
                        size = int(shm_size)
                        # Try to attach to existing SHM with various name formats
                        # Key issue: Rust 'shared_memory' vs Python 'multiprocessing.shared_memory' naming on macOS
                        candidates = [shm_key]
                        if shm_key.startswith('/'):
                            candidates.append(shm_key[1:]) # Try without slash
                        else:
                            candidates.append('/' + shm_key) # Try with slash
                        
                        existing_shm = None
                        last_error = None
                        
                        for name in candidates:
                            try:
                                existing_shm = shared_memory.SharedMemory(name=name)
                                break
                            except Exception as e:
                                last_error = e
                        
                        if existing_shm is None:
                            raise last_error

                        # Read data directly from memory
                        # Note: In real world, we might use memoryview to avoid copy, 
                        # but for this string-based demo we decode it.
                        body = bytes(existing_shm.buf[:size]).decode('utf-8')
                        transport_method = f"SHARED MEMORY ({shm_key})"
                        existing_shm.close() # Detach
                    except Exception as e:
                        print(f"Error reading SHM: {e}")
                        self.send_error(500, f"Shared Memory Error: {str(e)}")
                        return
                else:
                    # Case 2: Standard Body via Socket
                    content_length = int(self.headers.get('Content-Length', 0))
                    if content_length > 0:
                        body = self.rfile.read(content_length).decode('utf-8')

                req = Request(self.path, method, self.headers, body)
                
                try:
                    resp_data = func(req)
                    if isinstance(resp_data, dict):
                        resp_data['_meta'] = {
                            "worker_pid": os.getpid(),
                            "transport": transport_method
                        }

                    resp_bytes = json.dumps(resp_data).encode('utf-8')
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(resp_bytes)
                except Exception as e:
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
