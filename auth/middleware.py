"""
Bearer JWT middleware for metrify-demo.

Extracts consumer_api_key from a valid JWT and stores it in a ContextVar so
tool handlers can resolve the key without requiring it as an explicit parameter.

Dual-auth flows:
  OAuth (Bearer JWT) — middleware sets _current_consumer_key from JWT "sub" claim.
                        Tool parameter consumer_api_key is ignored.
  Legacy (parameter)  — no Bearer header; tool reads consumer_api_key from its
                        own parameter. Fully backwards compatible.
"""
from contextvars import ContextVar
from typing import Optional

import jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from auth.jwt_validator import JWTValidator


# ContextVar: holds the consumer API key resolved from a Bearer JWT for the
# current async task (i.e., the current HTTP request).
# None when no Bearer token was presented — legacy parameter flow is used.
_current_consumer_key: ContextVar[Optional[str]] = ContextVar(
    "current_consumer_key", default=None
)


class BearerMiddleware(BaseHTTPMiddleware):
    """ASGI middleware: validates Bearer JWT and populates _current_consumer_key.

    Happy path (valid JWT):
      Authorization: Bearer <token>
      → payload["sub"] stored in _current_consumer_key for the request lifetime
      → downstream tools resolve the key without consumer_api_key parameter

    No header:
      → passes through; tool reads consumer_api_key from its own parameter

    Error responses (returned before the tool is invoked):
      401 {"error": "token_expired"}  — JWT has expired
      401 {"error": "invalid_token"}  — JWT is invalid for any other reason
    """

    def __init__(self, app, validator: JWTValidator) -> None:
        super().__init__(app)
        self._validator = validator

    async def dispatch(self, request: Request, call_next):
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
            try:
                payload = await self._validator.validate(token)
                _current_consumer_key.set(payload["sub"])
            except jwt.ExpiredSignatureError:
                return JSONResponse(
                    {
                        "error": "token_expired",
                        "message": (
                            "Token OAuth expirado. Re-autenticá en Claude Desktop."
                        ),
                    },
                    status_code=401,
                )
            except jwt.PyJWTError:
                return JSONResponse(
                    {
                        "error": "invalid_token",
                        "message": "Token OAuth inválido.",
                    },
                    status_code=401,
                )
        response = await call_next(request)
        return response
