import pickle
import base64
from fastapi import FastAPI, Request
from pydantic import BaseModel
import uvicorn
import sys
import threading

# We need to import the registry of services.
# Since this module will be imported by api.py or vice versa, we need to be careful with circular imports.
# We will inject the services dict or import it at runtime.

app = FastAPI()

# Global reference to the function registry
_services_registry = {}

def set_registry(registry):
    global _services_registry
    _services_registry = registry

class CallRequest(BaseModel):
    args_pickle_b64: str  # Base64 encoded pickled tuple of args

@app.post("/call/{service_name}")
async def call_service(service_name: str, request: CallRequest):
    if service_name not in _services_registry:
        return {"error": "Service not found", "status": "error"}
    
    func = _services_registry[service_name]
    
    # Decode args
    try:
        args_bytes = base64.b64decode(request.args_pickle_b64)
        args = pickle.loads(args_bytes)
    except Exception as e:
        return {"error": f"Deserialization error: {str(e)}", "status": "error"}
    
    # Execute
    try:
        if not isinstance(args, (list, tuple)):
            args = (args,)
        result = func(*args)
        
        # Serialize result
        result_bytes = pickle.dumps(result)
        result_b64 = base64.b64encode(result_bytes).decode('utf-8')
        
        return {"result_pickle_b64": result_b64, "status": "ok"}
    except Exception as e:
        # Print stacktrace for debug
        import traceback
        traceback.print_exc()
        return {"error": str(e), "status": "error"}

def run_server(host, port, registry):
    set_registry(registry)
    print(f"[ControlPlane] Starting HTTP server on {host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="warning")

def start_background_server(host, port, registry):
    t = threading.Thread(target=run_server, args=(host, port, registry), daemon=True)
    t.start()
