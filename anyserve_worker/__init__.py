"""
anyServe Python Worker - Execution Plane

This worker is spawned by Rust Runtime as a subprocess.
Communication is via Stdio (JSON lines).

Protocol:
- Input (from Rust): JSON line with {"op": "infer", "capability": "...", "inputs": "...", "input_refs": [...]}
- Output (to Rust): JSON line with {"output": "...", "output_refs": [...], "error": null}
"""
import sys
import json
import time
import os
import uuid

# Configuration
DATA_DIR = os.environ.get("ANYSERVE_DATA_DIR", "/tmp/anyserve_data")
LARGE_OUTPUT_THRESHOLD = 1000  # bytes


class Worker:
    def __init__(self):
        self.current_capability = None
        os.makedirs(DATA_DIR, exist_ok=True)
        print(f"[Worker] Initialized. Data dir: {DATA_DIR}", file=sys.stderr)
    
    def mock_switch_model(self, capability: str):
        """Simulate model switching overhead."""
        if self.current_capability != capability:
            print(f"[Worker] Switching from '{self.current_capability}' to '{capability}'...", file=sys.stderr)
            time.sleep(2)  # Simulate switching cost
            self.current_capability = capability
            print(f"[Worker] Switch complete.", file=sys.stderr)
    
    def mock_inference(self, inputs: str, capability: str) -> str:
        """Simulate inference - reverse string or append text."""
        print(f"[Worker] Processing '{capability}' with input length {len(inputs)}", file=sys.stderr)
        time.sleep(1)  # Simulate inference time
        
        if capability == "small":
            # Simple: reverse the input
            return inputs[::-1]
        elif capability == "large":
            # Heavy: append repeated text
            return f"LARGE_RESULT: {inputs}" + ("*" * 500)
        else:
            return f"[{capability}] processed: {inputs}"
    
    def save_to_fs(self, data: str) -> str:
        """Save large data to filesystem and return reference."""
        ref_id = str(uuid.uuid4())
        path = os.path.join(DATA_DIR, ref_id)
        with open(path, 'w') as f:
            f.write(data)
        print(f"[Worker] Saved large output to {path}", file=sys.stderr)
        return ref_id
    
    def load_from_fs(self, ref: str) -> str:
        """Load data from filesystem reference."""
        path = os.path.join(DATA_DIR, ref)
        if os.path.exists(path):
            with open(path, 'r') as f:
                return f.read()
        return ""
    
    def process_request(self, request: dict) -> dict:
        """Process a single request."""
        op = request.get("op", "")
        
        if op != "infer":
            return {"output": "", "output_refs": [], "error": f"Unknown op: {op}"}
        
        capability = request.get("capability", "")
        inputs = request.get("inputs", "")
        input_refs = request.get("input_refs", [])
        
        try:
            # Load any input references
            if input_refs:
                for ref in input_refs:
                    loaded = self.load_from_fs(ref)
                    inputs += loaded
            
            # Simulate model switch
            self.mock_switch_model(capability)
            
            # Simulate inference
            result = self.mock_inference(inputs, capability)
            
            # Check if output is large
            output_refs = []
            if len(result) > LARGE_OUTPUT_THRESHOLD:
                ref = self.save_to_fs(result)
                output_refs.append(ref)
                result = ""  # Clear output, use ref instead
            
            return {"output": result, "output_refs": output_refs, "error": None}
        
        except Exception as e:
            return {"output": "", "output_refs": [], "error": str(e)}
    
    def run(self):
        """Main loop - read JSON lines from stdin, process, write to stdout."""
        print("[Worker] Starting main loop...", file=sys.stderr)
        
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            
            try:
                request = json.loads(line)
                response = self.process_request(request)
                print(json.dumps(response), flush=True)
            except json.JSONDecodeError as e:
                error_response = {"output": "", "output_refs": [], "error": f"JSON parse error: {e}"}
                print(json.dumps(error_response), flush=True)
            except Exception as e:
                error_response = {"output": "", "output_refs": [], "error": f"Worker error: {e}"}
                print(json.dumps(error_response), flush=True)
        
        print("[Worker] Exiting.", file=sys.stderr)


def main():
    worker = Worker()
    worker.run()


if __name__ == "__main__":
    main()
