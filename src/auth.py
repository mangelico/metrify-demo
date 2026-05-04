import hashlib
import secrets

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models.api_key import ApiKey
from src.models.wallet import Wallet

_KEY_PREFIX = "mk_live_"


def generate_raw_key() -> str:
    return _KEY_PREFIX + secrets.token_urlsafe(32)


def hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


async def require_api_key(
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> Wallet:
    key_hash = hash_key(x_api_key)

    result = await db.execute(
        select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.is_active.is_(True))
    )
    api_key = result.scalar_one_or_none()

    if api_key is None:
        raise HTTPException(status_code=401, detail={"error": "invalid_api_key"})

    wallet = await db.get(Wallet, api_key.wallet_id)
    if wallet is None:
        raise HTTPException(status_code=401, detail={"error": "invalid_api_key"})

    return wallet
