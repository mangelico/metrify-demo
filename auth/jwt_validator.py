"""
JWT validator for metrify-demo Bearer authentication.

Validates JWT tokens issued by metrify-backend using HS256 (shared secret).

Option A audience: accepts tokens where "metrify-demo" is one of the audiences.
The backend issues aud=["metrify-mcp", "metrify-demo"] so the same token works
for both MCP servers. In V2 this can be restricted to metrify-demo only.

Environment variables:
    JWT_SECRET  — shared secret for HS256 signature verification
    JWT_ISSUER  — expected issuer claim (optional; skipped if not set)
"""
import os
from typing import Any, Dict, List, Optional

import jwt


# This service's audience claim.
# Option A: the backend emits aud=["metrify-mcp", "metrify-demo"] for a single
# token valid at both MCP servers. PyJWT validates that THIS_AUDIENCE is
# present in the token's aud field — so aud=["metrify-mcp", "metrify-demo"]
# passes when we require "metrify-demo".
THIS_AUDIENCE = "metrify-demo"


class JWTValidator:
    """Validates Bearer JWT tokens.

    Usage:
        validator = JWTValidator()  # reads JWT_SECRET / JWT_ISSUER from env
        payload = await validator.validate(token_string)
        consumer_key = payload["sub"]  # Metrify consumer api_key

    Raises:
        jwt.ExpiredSignatureError  — token has expired (caller returns 401)
        jwt.PyJWTError             — any other validation failure (caller returns 401)
    """

    def __init__(
        self,
        secret: Optional[str] = None,
        issuer: Optional[str] = None,
        algorithms: Optional[List[str]] = None,
    ) -> None:
        self._secret: str = secret or os.environ.get("JWT_SECRET", "")
        self._issuer: Optional[str] = issuer or os.environ.get("JWT_ISSUER") or None
        self._algorithms: List[str] = algorithms or ["HS256"]

    async def validate(self, token: str) -> Dict[str, Any]:
        """Validate a JWT Bearer token and return the decoded payload.

        Args:
            token: Raw JWT string (without the "Bearer " prefix).

        Returns:
            Decoded payload dict. The "sub" claim holds the consumer's api_key.

        Raises:
            jwt.ExpiredSignatureError: Token has expired.
            jwt.PyJWTError: Token is invalid (bad signature, wrong audience, etc.).
        """
        decode_kwargs: Dict[str, Any] = {
            "algorithms": self._algorithms,
            "audience": THIS_AUDIENCE,
        }
        if self._issuer:
            decode_kwargs["issuer"] = self._issuer

        payload: Dict[str, Any] = jwt.decode(
            token,
            self._secret,
            **decode_kwargs,
        )
        return payload
