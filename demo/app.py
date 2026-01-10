from miniserve import App

app = App()

# 用户只需关注逻辑，就像 FastAPI
@app.route("/", method="GET")
def index(req):
    return {"message": "Hello from User App"}

@app.route("/process", method="POST")
def process(req):
    return {
        "action": "processed",
        "input_len": len(req.body) if req.body else 0,
        "raw_input": req.body
    }

if __name__ == "__main__":
    # 1. 独立运行时：默认 8000，单进程，方便 Debug
    # 2. 被 Rust 调用时：Rust 会传入 --port 参数，覆盖默认值
    app.run()
