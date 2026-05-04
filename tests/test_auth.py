import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from src.auth import generate_raw_key, hash_key, require_admin_token, require_api_key
from src.models.api_key import ApiKey
from src.models.wallet import Wallet


def test_generate_raw_key_format():
    key = generate_raw_key()
    assert key.startswith("mk_live_")
    assert len(key) > 20


def test_hash_key_deterministic():
    key = "mk_live_testkey"
    assert hash_key(key) == hash_key(key)
    assert len(hash_key(key)) == 64


def test_hash_key_different_inputs():
    assert hash_key("key_a") != hash_key("key_b")


@pytest.mark.asyncio
async def test_require_api_key_valid():
    wallet_id = uuid.uuid4()
    raw_key = "mk_live_validkey"

    mock_api_key = MagicMock(spec=ApiKey)
    mock_api_key.wallet_id = wallet_id

    mock_wallet = MagicMock(spec=Wallet)
    mock_wallet.id = wallet_id

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_api_key

    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result
    mock_db.get.return_value = mock_wallet

    wallet = await require_api_key(x_api_key=raw_key, db=mock_db)
    assert wallet is mock_wallet


@pytest.mark.asyncio
async def test_require_api_key_invalid_returns_401():
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result

    with pytest.raises(HTTPException) as exc_info:
        await require_api_key(x_api_key="mk_live_badkey", db=mock_db)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == {"error": "invalid_api_key"}


@pytest.mark.asyncio
async def test_require_admin_token_valid():
    await require_admin_token(x_admin_token="test-admin-token")


@pytest.mark.asyncio
async def test_require_admin_token_invalid():
    with pytest.raises(HTTPException) as exc_info:
        await require_admin_token(x_admin_token="wrong-token")
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == {"error": "invalid_admin_token"}


@pytest.mark.asyncio
async def test_require_api_key_missing_wallet_returns_401():
    wallet_id = uuid.uuid4()

    mock_api_key = MagicMock(spec=ApiKey)
    mock_api_key.wallet_id = wallet_id

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_api_key

    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result
    mock_db.get.return_value = None  # wallet deleted / orphaned

    with pytest.raises(HTTPException) as exc_info:
        await require_api_key(x_api_key="mk_live_somekey", db=mock_db)

    assert exc_info.value.status_code == 401
