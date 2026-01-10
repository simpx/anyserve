class MyBigData:
    def __init__(self, size):
        self.payload = "x" * size

    def __repr__(self):
        return f"<MyBigData size={len(self.payload)}>"
