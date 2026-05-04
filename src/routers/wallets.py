import uuid
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import require_admin_token
from src.database import get_db
from src.models.wallet import Wallet

router = APIRouter(prefix="/wallets", tags=["wallets"])


class CreateWalletRequest(BaseModel):
    agent_id: str
    master_id: Optional[str] = None


class WalletResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agent_id: str
    master_id: Optional[str]
    balance_usdt: Decimal


class TopupRequest(BaseModel):
    amount: Decimal = Field(..., gt=0, description="Amount in USDT to add")


class TopupResponse(BaseModel):
    wallet_id: uuid.UUID
    added: Decimal
    balance_usdt: Decimal


@router.post("", response_model=WalletResponse, status_code=201, dependencies=[Depends(require_admin_token)])
async def create_wallet(
    body: CreateWalletRequest,
    db: AsyncSession = Depends(get_db),
) -> WalletResponse:
    wallet = Wallet(agent_id=body.agent_id, master_id=body.master_id)
    db.add(wallet)
    try:
        await db.commit()
        await db.refresh(wallet)
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=409, detail={"error": "agent_id_already_exists"})
    return WalletResponse.model_validate(wallet)


@router.get("/{wallet_id}", response_model=WalletResponse)
async def get_wallet(
    wallet_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> WalletResponse:
    wallet = await db.get(Wallet, wallet_id)
    if wallet is None:
        raise HTTPException(status_code=404, detail={"error": "wallet_not_found"})
    return WalletResponse.model_validate(wallet)


@router.post("/{wallet_id}/topup", response_model=TopupResponse, dependencies=[Depends(require_admin_token)])
async def topup_wallet(
    wallet_id: uuid.UUID,
    body: TopupRequest,
    db: AsyncSession = Depends(get_db),
) -> TopupResponse:
    wallet = await db.get(Wallet, wallet_id)
    if wallet is None:
        raise HTTPException(status_code=404, detail={"error": "wallet_not_found"})

    wallet.balance_usdt = Decimal(str(wallet.balance_usdt)) + body.amount
    await db.commit()
    await db.refresh(wallet)

    return TopupResponse(
        wallet_id=wallet.id,
        added=body.amount,
        balance_usdt=Decimal(str(wallet.balance_usdt)),
    )
