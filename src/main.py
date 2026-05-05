from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from src.limiter import limiter
from src.routers import dashboard, health, keys, mcp, wallets

app = FastAPI(title="Modelo Gateway", version="0.1.0")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(health.router)
app.include_router(keys.router)
app.include_router(wallets.router)
app.include_router(mcp.router)
app.include_router(dashboard.router)
