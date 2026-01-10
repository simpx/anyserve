import sys
import os
import argparse
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        
        response = {
            "message": "Hello from Python Worker",
            "pid": os.getpid(),
            "port": self.server.server_port
        }
        self.wfile.write(json.dumps(response).encode())

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        
        response = {
            "message": "Processed by Python Worker",
            "pid": os.getpid(),
            "data_received": post_data.decode('utf-8')
        }
        self.wfile.write(json.dumps(response).encode())

def run(port):
    server_address = ('127.0.0.1', port)
    httpd = HTTPServer(server_address, SimpleHandler)
    print(f"Python Worker (PID: {os.getpid()}) starting on port {port}...", flush=True)
    httpd.serve_forever()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True, help="Port to listen on")
    args = parser.parse_args()
    
    run(args.port)
