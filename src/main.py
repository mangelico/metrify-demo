from fastapi import FastAPI

from src.routers import health

app = FastAPI(title="Modelo Gateway", version="0.1.0")

app.include_router(health.router)
