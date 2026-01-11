from miniserve import App

app = App()

# 用户只需关注逻辑，就像 FastAPI
@app.route("/", method="GET")
def index(req):
    return {"message": "Hello from User App"}

@app.route("/process", method="POST")
def process(req):
    # Check if input is bytes or memoryview (Zero-Copy path)
    if isinstance(req.body, (bytes, memoryview)):
        # Example 1: High-Performance JSON Deserialization
        # json.loads accepts bytes/bytearray directly. 
        # For memoryview, we must cast to bytes efficiently or use a library that supports buffer protocol.
        try:
            # fast path if input is JSON
            parsed_json = json.loads(req.body) 
            return {
                "action": "parsed_json",
                "content": parsed_json,
                "data_type": str(type(req.body))
            }
        except Exception:
            # Fallback if not JSON: Treat as string
            text = bytes(req.body).decode('utf-8')
            return {
                "action": "processed_text",
                "input_len": len(req.body),
                "raw_input": text, # We decode it just for the response
                "data_type": str(type(req.body))
            }

    return {
        "action": "processed_legacy",
        "input_len": len(req.body) if req.body else 0,
        "raw_input": req.body
    }

if __name__ == "__main__":
    # 1. 独立运行时：默认 8000，单进程，方便 Debug
    # 2. 被 Rust 调用时：Rust 会传入 --port 参数，覆盖默认值
    app.run()
