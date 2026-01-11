import sys
import os

# Ensure we can import 
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from anyserve_worker import Client

def main():
    target = "localhost:8080" # The port we used in previous example
    print(f"Connecting to {target}...")
    
    client = Client(target)
    
    if not client.is_alive():
        print("Server is not alive!")
        return

    print("Server is alive.")
    
    if client.is_model_ready("cli_test"):
        print("Model 'cli_test' is ready.")
        
        # Infer
        print("Calling cli_test...")
        # Since cli_test implementation just returns empty response with model name,
        # let's expect no outputs, but successful call.
        res = client.infer("cli_test", inputs={"test_in": [1, 2, 3]})
        print(f"Result: {res}")
        
    else:
        print("Model 'cli_test' not found.")

if __name__ == "__main__":
    main()
