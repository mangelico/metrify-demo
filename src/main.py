from fastapi import FastAPI

from src.routers import health
from src.routers import keys

app = FastAPI(title="Modelo Gateway", version="0.1.0")

app.include_router(health.router)
app.include_router(keys.router)
