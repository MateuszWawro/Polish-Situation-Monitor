from fastapi import FastAPI

app = FastAPI(title="Polish Situation Monitor API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
