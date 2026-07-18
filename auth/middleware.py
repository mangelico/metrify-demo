"""
Bearer JWT middleware for metrify-demo.

Also serves RFC 9728 Protected Resource Metadata at:
  GET /.well-known/oauth-protected-resource  (no auth required)

This endpoint lets OAuth clients (e.g. Claude Desktop) discover the
Authorization Server automatically from the WWW-Authenticate header on
any 401 response.

Auth flows:
  Valid JWT   → payload["sub"] stored in _current_consumer_key for the request
  No Bearer   → 401 unauthorized  + WWW-Authenticate (enables auto-discovery)
  Expired JWT → 401 token_expired + WWW-Authenticate
  Invalid JWT → 401 invalid_token + WWW-Authenticate

Environment variables:
  MCP_BASE_URL         — public base URL of this server, no trailing slash
                         e.g. https://web-production-b51ff.up.railway.app
  METRIFY_BACKEND_URL  — URL of the Authorization Server (metrify-backend)
"""
import logging
import os
from contextvars import ContextVar
from typing import Any, Dict, Optional

import jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from auth.jwt_validator import JWTValidator

logger = logging.getLogger(__name__)


# ContextVar: holds the consumer API key resolved from a Bearer JWT for the
# current async task (i.e. the current HTTP request).
# None when the middleware let the request through without a JWT (shouldn't
# happen in production — middleware blocks all non-JWT requests).
_current_consumer_key: ContextVar[Optional[str]] = ContextVar(
    "current_consumer_key", default=None
)

_METADATA_PATH = "/.well-known/oauth-protected-resource"


class BearerMiddleware(BaseHTTPMiddleware):
    """ASGI middleware: RFC 9728 metadata + Bearer JWT enforcement.

    On init, reads MCP_BASE_URL and METRIFY_BACKEND_URL from the environment
    to build:
      - _metadata   : JSON body for the public discovery endpoint
      - _www_authenticate : WWW-Authenticate header value on all 401 responses
    """

    def __init__(self, app, validator: JWTValidator) -> None:
        super().__init__(app)
        self._validator = validator

        mcp_base_url = os.environ.get(
            "MCP_BASE_URL", "http://localhost:8000"
        ).rstrip("/")
        backend_url = os.environ.get("METRIFY_BACKEND_URL", "")

        # RFC 9728 §3 — Protected Resource Metadata
        self._metadata: Dict[str, Any] = {
            "resource": f"{mcp_base_url}/mcp",
            "authorization_servers": [backend_url],
            "bearer_methods_supported": ["header"],
            "resource_documentation": f"{mcp_base_url}/docs",
        }

        # RFC 6750 §3 + RFC 9728 §5.1 — WWW-Authenticate on 401
        self._www_authenticate: str = (
            f'Bearer resource_metadata="{mcp_base_url}{_METADATA_PATH}"'
        )

    async def dispatch(self, request: Request, call_next):
        # ── Public: RFC 9728 metadata endpoint (no auth required) ──────────
        if request.url.path == _METADATA_PATH:
            return JSONResponse(self._metadata)

        # ── All other paths require a Bearer JWT ────────────────────────────
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return JSONResponse(
                {"error": "unauthorized", "message": "Bearer token required"},
                status_code=401,
                headers={"WWW-Authenticate": self._www_authenticate},
            )

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
                headers={"WWW-Authenticate": self._www_authenticate},
            )
        except jwt.PyJWTError as exc:
            logger.warning("JWT validation failed: %s: %s", type(exc).__name__, exc)
            return JSONResponse(
                {
                    "error": "invalid_token",
                    "message": "Token OAuth inválido.",
                },
                status_code=401,
                headers={"WWW-Authenticate": self._www_authenticate},
            )

        response = await call_next(request)
        return response
