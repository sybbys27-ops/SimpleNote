from fastapi import FastAPI

app = FastAPI(title="SimpleNote API")


@app.get("/health")
def health():
    return {"status": "ok"}
