from fastapi import FastAPI
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.requests import Request

from src.limiter import limiter
from src.routers import dashboard, health, keys, mcp, wallets


def _rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    response = JSONResponse(
        {"error": "rate_limit_exceeded", "detail": str(exc.detail)},
        status_code=429,
    )
    retry_after = getattr(exc, "retry_after", None)
    response.headers["Retry-After"] = str(retry_after) if retry_after else "60"
    return response


app = FastAPI(title="Modelo Gateway", version="0.1.0")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(health.router)
app.include_router(keys.router)
app.include_router(wallets.router)
app.include_router(mcp.router)
app.include_router(dashboard.router)
