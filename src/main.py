from fastapi import FastAPI

from src.routers import dashboard, health, keys, mcp, wallets

app = FastAPI(title="Modelo Gateway", version="0.1.0")

app.include_router(health.router)
app.include_router(keys.router)
app.include_router(wallets.router)
app.include_router(mcp.router)
app.include_router(dashboard.router)
