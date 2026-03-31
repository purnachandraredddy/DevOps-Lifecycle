from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"message": "hello"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/ready")
def ready():
    return {"ready": True}
