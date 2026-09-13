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
                           (e.g. https://api.metrify.dev)
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

    async def _get_public_key(
        self, kid: Optional[str] = None, force_refresh: bool = False
    ) -> Any:
        """Fetch the RSA public key from the backend JWKS endpoint (cached).

        Fetches {METRIFY_BACKEND_URL}/oauth/jwks.json on first call (or when
        force_refresh=True), selects the key matching `kid`, and caches the
        result.

        Selection rules:
          - kid given, matches a published key -> that key.
          - kid given, matches nothing -> rejected. We have no key that
            could possibly verify this token, so we don't silently fall
            back to a different one -- this matters once the JWKS ever
            carries more than one key (e.g. during a rotation).
          - kid absent, exactly one key published -> that key. Unambiguous:
            there's no other candidate it could be. This is the one case
            the previous unconditional "fall back to the first key" was
            actually justified for (single-key deployments), so it's kept.
          - kid absent, more than one key published -> rejected. With
            nothing to disambiguate on, guessing keys[0] would reintroduce
            exactly the problem above.

        Args:
            kid: `kid` header from the token being validated, used to pick
                the matching JWKS entry so key rotation with multiple
                published keys resolves to the right one.
            force_refresh: bypass the cache and re-fetch even if a key is
                already cached. Used to recover from a backend key rotation:
                without this, a process that cached the old key at startup
                would reject every token signed with the new key until it
                was restarted.

        Returns:
            RSA public key object usable by PyJWT.

        Raises:
            httpx.HTTPError: JWKS endpoint unreachable or returned an error.
            KeyError / ValueError: JWKS response is malformed.
            jwt.InvalidSignatureError: no published key can be identified
                for this token (see selection rules above).
        """
        if self._public_key is not None and not force_refresh:
            return self._public_key

        url = f"{self._backend_url}{JWKS_PATH}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=10.0)
            resp.raise_for_status()
            jwks = resp.json()

        keys = jwks["keys"]
        if kid:
            key_data = next((k for k in keys if k.get("kid") == kid), None)
            if key_data is None:
                raise jwt.InvalidSignatureError(
                    f"No JWKS key found matching kid={kid!r}"
                )
        elif len(keys) == 1:
            key_data = keys[0]
        else:
            raise jwt.InvalidSignatureError(
                "Token has no kid and JWKS publishes multiple keys — "
                "cannot determine which key to verify against"
            )
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
        kid = jwt.get_unverified_header(token).get("kid")
        public_key = await self._get_public_key(kid=kid)

        decode_kwargs: Dict[str, Any] = {
            "algorithms": ["RS256"],
            "audience": self._resource_url,
        }
        if self._issuer:
            decode_kwargs["issuer"] = self._issuer

        try:
            return jwt.decode(token, public_key, **decode_kwargs)
        except jwt.InvalidSignatureError:
            # Cached key may be stale after a backend key rotation — refetch
            # once and retry before giving up. Any other failure (expired,
            # wrong audience, malformed) is a real rejection, not a caching
            # problem, so only this specific exception triggers a refetch.
            public_key = await self._get_public_key(kid=kid, force_refresh=True)
            return jwt.decode(token, public_key, **decode_kwargs)
