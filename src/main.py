from fastapi import FastAPI


app = FastAPI(title="Production Control API", version="0.1.0")


@app.get("/health", tags=["health"])
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
