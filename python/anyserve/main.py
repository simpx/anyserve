from typing import Union
from fastapi import FastAPI
from anyserve._core import sum_as_string

app = FastAPI()

@app.get("/")
def read_root():
    return {"Hello": "World", "Rust_Says": sum_as_string(10, 20)}

@app.get("/add/{a}/{b}")
def add(a: int, b: int):
    result = sum_as_string(a, b)
    return {"a": a, "b": b, "sum_as_string": result}
