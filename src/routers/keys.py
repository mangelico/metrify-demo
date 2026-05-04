import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import generate_raw_key, hash_key, require_admin_token
from src.database import get_db
from src.models.api_key import ApiKey
from src.models.wallet import Wallet

router = APIRouter(prefix="/keys", tags=["keys"])


class CreateKeyRequest(BaseModel):
    wallet_id: uuid.UUID
    label: Optional[str] = None


class CreateKeyResponse(BaseModel):
    key: str
    key_id: uuid.UUID
    wallet_id: uuid.UUID
    label: Optional[str]


@router.post("", response_model=CreateKeyResponse, status_code=201, dependencies=[Depends(require_admin_token)])
async def create_api_key(
    body: CreateKeyRequest,
    db: AsyncSession = Depends(get_db),
) -> CreateKeyResponse:
    wallet = await db.get(Wallet, body.wallet_id)
    if wallet is None:
        raise HTTPException(status_code=404, detail={"error": "wallet_not_found"})

    raw_key = generate_raw_key()
    api_key = ApiKey(
        key_hash=hash_key(raw_key),
        wallet_id=body.wallet_id,
        label=body.label,
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)

    return CreateKeyResponse(
        key=raw_key,
        key_id=api_key.id,
        wallet_id=api_key.wallet_id,
        label=api_key.label,
    )


@router.get("/verify", status_code=200)
async def verify_key(
    x_api_key: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Dev utility — checks if a raw key is valid without hitting a protected route."""
    from src.auth import hash_key as _hash

    result = await db.execute(
        select(ApiKey).where(
            ApiKey.key_hash == _hash(x_api_key), ApiKey.is_active.is_(True)
        )
    )
    api_key = result.scalar_one_or_none()
    if api_key is None:
        raise HTTPException(status_code=401, detail={"error": "invalid_api_key"})
    return {"valid": True, "wallet_id": str(api_key.wallet_id)}
