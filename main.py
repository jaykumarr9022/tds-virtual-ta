from fastapi import FastAPI

app = FastAPI()  # <-- This line is required!

@app.get("/")
def read_root():
    return {"message": "TDS Virtual TA API is running!"}
