import sys
import os

# Ensure we can import anyserve_worker
# In production this happens automatically
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from anyserve_worker import Worker, ModelInferResponse

app = Worker()

@app.model("cli_test")
def impl(request):
    print(f"[CLITest] Called!", file=sys.stderr)
    return ModelInferResponse(model_name=request.model_name)
