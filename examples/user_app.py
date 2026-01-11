import sys
import os

# Ensure we can import anyserve_worker which is at root/anyserve_worker
# In production this would be installed via pip
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from anyserve_worker import Worker, ModelInferResponse

app = Worker()

@app.model("math_double")
def double_values(request):
    """
    A simple user-defined capability that doubles the input values.
    Expects INT32 inputs.
    """
    print(f"[UserApp] Received request for {request.model_name}, id={request.id}", file=sys.stderr)
    
    response = ModelInferResponse(
        model_name=request.model_name,
        model_version=request.model_version,
        id=request.id
    )
    
    for inp in request.inputs:
        out = response.outputs.add()
        out.name = inp.name
        out.datatype = inp.datatype
        out.shape.extend(inp.shape)
        
        # Double the values
        if len(inp.contents.int_contents) > 0:
            new_vals = [x * 2 for x in inp.contents.int_contents]
            out.contents.int_contents.extend(new_vals)
        else:
            print(f"[UserApp] Warning: Input {inp.name} has no int_contents", file=sys.stderr)
            
    return response

if __name__ == "__main__":
    print("[UserApp] Starting user application...", file=sys.stderr)
    app.serve()
