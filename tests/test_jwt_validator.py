"""
Tests for JWTValidator's key-selection logic in auth/jwt_validator.py --
specifically _get_public_key()'s kid handling.

Previously, a token whose `kid` didn't match any published JWKS key still
silently fell back to keys[0] instead of being rejected (harmless with
today's single-key JWKS, but would have accepted a token signed under the
wrong key the day a rotation adds a second one). Now it's rejected.

Fully offline: RSA test keypairs generated in-process, respx mocks the
JWKS HTTP endpoint. Matches this repo's existing respx style
(tests/test_billing.py). tests/test_jwt_middleware.py pre-injects
_public_key to skip this code path entirely, so it's unaffected by (and
doesn't cover) what's tested here.
"""
import json
import time

import httpx
import jwt as pyjwt
import pytest
import respx
from cryptography.hazmat.primitives.asymmetric import rsa

from auth.jwt_validator import JWTValidator

BACKEND_URL = "https://test-backend.metrify.local"
ISSUER = BACKEND_URL
RESOURCE_URL = "https://test-provider.example.com/mcp"
JWKS_URL = f"{BACKEND_URL}/oauth/jwks.json"

# The kid metrify-backend actually issues in production today -- decoded
# from a live token during this session's testing (see
# API_KEY_EXCHANGE_TEST.md in metrify-agent): header was
# {"alg": "RS256", "kid": "metrify-rs256-key", "typ": "JWT"}.
PRODUCTION_KID = "metrify-rs256-key"

_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_PUBLIC_KEY = _PRIVATE_KEY.public_key()

# A second, unrelated keypair -- decoy key / wrong-key signer.
_OTHER_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_OTHER_PUBLIC_KEY = _OTHER_PRIVATE_KEY.public_key()


def _jwk(public_key, kid: str) -> dict:
    jwk = json.loads(pyjwt.algorithms.RSAAlgorithm.to_jwk(public_key))
    jwk["kid"] = kid
    return jwk


def _make_token(private_key=_PRIVATE_KEY, kid=None, aud=RESOURCE_URL, exp_offset=3600) -> str:
    payload = {
        "sub": "ck_live_test",
        "aud": aud,
        "iss": ISSUER,
        "iat": int(time.time()),
        "exp": int(time.time()) + exp_offset,
    }
    headers = {"kid": kid} if kid else {}
    return pyjwt.encode(payload, private_key, algorithm="RS256", headers=headers)


def _validator() -> JWTValidator:
    return JWTValidator(backend_url=BACKEND_URL, issuer=ISSUER, resource_url=RESOURCE_URL)


@respx.mock
async def test_unmatched_kid_is_rejected():
    """kid on the token matches nothing in the JWKS -> rejected, not keys[0]."""
    jwks = {"keys": [_jwk(_PUBLIC_KEY, "some-other-kid")]}
    respx.get(JWKS_URL).mock(return_value=httpx.Response(200, json=jwks))
    token = _make_token(kid="kid-that-does-not-exist-anywhere")

    with pytest.raises(pyjwt.InvalidSignatureError):
        await _validator().validate(token)


@respx.mock
async def test_matched_kid_in_multi_key_jwks_uses_correct_key_not_first():
    """Two keys published, decoy first -- must use the one the kid actually points at."""
    jwks = {"keys": [_jwk(_OTHER_PUBLIC_KEY, "decoy-kid"), _jwk(_PUBLIC_KEY, "real-kid")]}
    respx.get(JWKS_URL).mock(return_value=httpx.Response(200, json=jwks))
    token = _make_token(kid="real-kid")  # signed with _PRIVATE_KEY, matching the SECOND jwk

    payload = await _validator().validate(token)

    assert payload["sub"] == "ck_live_test"


@respx.mock
async def test_production_kid_still_validates():
    """The one that matters most: today's real backend issues kid='metrify-rs256-key'."""
    jwks = {"keys": [_jwk(_PUBLIC_KEY, PRODUCTION_KID)]}
    respx.get(JWKS_URL).mock(return_value=httpx.Response(200, json=jwks))
    token = _make_token(kid=PRODUCTION_KID)

    payload = await _validator().validate(token)

    assert payload["sub"] == "ck_live_test"


@respx.mock
async def test_no_kid_single_key_jwks_still_works():
    """No kid on the token, exactly one key published -> unambiguous, still allowed."""
    jwks = {"keys": [_jwk(_PUBLIC_KEY, PRODUCTION_KID)]}
    respx.get(JWKS_URL).mock(return_value=httpx.Response(200, json=jwks))
    token = _make_token(kid=None)

    payload = await _validator().validate(token)

    assert payload["sub"] == "ck_live_test"


@respx.mock
async def test_no_kid_multi_key_jwks_is_rejected():
    """No kid on the token, MULTIPLE keys published -> ambiguous, rejected."""
    jwks = {"keys": [_jwk(_PUBLIC_KEY, "kid-a"), _jwk(_OTHER_PUBLIC_KEY, "kid-b")]}
    respx.get(JWKS_URL).mock(return_value=httpx.Response(200, json=jwks))
    token = _make_token(kid=None)

    with pytest.raises(pyjwt.InvalidSignatureError):
        await _validator().validate(token)
