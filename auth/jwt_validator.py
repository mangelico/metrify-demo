"""
JWT validator for metrify-demo Bearer authentication.

Validates JWT tokens issued by metrify-backend using RS256 (asymmetric).
The public key is fetched once from the backend's JWKS endpoint and cached
in memory — no shared secret required.

RS256 vs HS256:
  HS256 (old) — every provider needs the same JWT_SECRET; secret distribution
                is a security risk in an open multi-provider network.
  RS256 (this) — metrify-demo only needs the public key, which is non-secret
                 and published at /oauth/jwks.json. Any provider can validate
                 tokens without ever touching a private key.

Environment variables:
    METRIFY_BACKEND_URL  — base URL of metrify-backend
                           (e.g. https://airy-wholeness-production-fcc4.up.railway.app)
    JWT_ISSUER           — expected issuer claim (optional; skipped if not set)
    MCP_BASE_URL         — public base URL of THIS server (no trailing slash).
                           Tokens must carry this server's own resource URL
                           (MCP_BASE_URL + "/mcp") in their "aud" claim — this
                           is the same value BearerMiddleware publishes as
                           "resource" in the RFC 9728 metadata endpoint, so
                           both must stay derived from the same env var.
"""
import json
import os
from typing import Any, Dict, Optional

import httpx
import jwt
from jwt.algorithms import RSAAlgorithm


# JWKS path relative to METRIFY_BACKEND_URL.
JWKS_PATH = "/oauth/jwks.json"


def _default_resource_url() -> str:
    """This server's own resource identifier — matches middleware.py's RFC 9728 'resource'."""
    base = os.environ.get("MCP_BASE_URL", "http://localhost:8000").rstrip("/")
    return f"{base}/mcp"


class JWTValidator:
    """Validates Bearer JWT tokens using RS256 + JWKS.

    Usage:
        validator = JWTValidator()       # reads env vars
        payload = await validator.validate(token_string)
        consumer_key = payload["sub"]    # Metrify consumer api_key

    The public key is fetched from the backend JWKS endpoint on first use
    and cached for the lifetime of the instance. No shared secret is needed.

    Raises:
        jwt.ExpiredSignatureError  — token has expired (caller returns 401)
        jwt.PyJWTError             — any other validation failure (caller returns 401)
    """

    def __init__(
        self,
        backend_url: Optional[str] = None,
        issuer: Optional[str] = None,
        resource_url: Optional[str] = None,
    ) -> None:
        self._backend_url: str = (
            backend_url or os.environ.get("METRIFY_BACKEND_URL", "")
        ).rstrip("/")
        self._issuer: Optional[str] = issuer or os.environ.get("JWT_ISSUER") or None
        self._resource_url: str = resource_url or _default_resource_url()
        self._public_key: Any = None  # cached after first JWKS fetch

    async def _get_public_key(self) -> Any:
        """Fetch the RSA public key from the backend JWKS endpoint (cached).

        Fetches {METRIFY_BACKEND_URL}/oauth/jwks.json on first call,
        parses the first RSA key with RSAAlgorithm.from_jwk(), and caches it.

        Returns:
            RSA public key object usable by PyJWT.

        Raises:
            httpx.HTTPError: JWKS endpoint unreachable or returned an error.
            KeyError / ValueError: JWKS response is malformed.
        """
        if self._public_key is not None:
            return self._public_key

        url = f"{self._backend_url}{JWKS_PATH}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=10.0)
            resp.raise_for_status()
            jwks = resp.json()

        # Use the first RSA key in the set.
        # V2: match by `kid` header in the incoming token for key rotation support.
        key_data = jwks["keys"][0]
        self._public_key = RSAAlgorithm.from_jwk(json.dumps(key_data))
        return self._public_key

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
        public_key = await self._get_public_key()

        decode_kwargs: Dict[str, Any] = {
            "algorithms": ["RS256"],
            "audience": self._resource_url,
        }
        if self._issuer:
            decode_kwargs["issuer"] = self._issuer

        payload: Dict[str, Any] = jwt.decode(token, public_key, **decode_kwargs)
        return payload
