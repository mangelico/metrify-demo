import uuid
from decimal import Decimal
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import require_api_key
from src.config import settings
from src.database import get_db
from src.models.transaction import TransactionStatus
from src.models.wallet import Wallet
from src.services.metering import InsufficientBalanceError, MeteringService
from src.wrappers.anthropic_wrapper import AnthropicWrapper
from src.wrappers.base import UpstreamError

router = APIRouter(prefix="/mcp", tags=["mcp"])

_WRAPPERS = {
    "anthropic": AnthropicWrapper(),
}


class MCPCallRequest(BaseModel):
    tool: str
    params: Dict[str, Any]
    idempotency_key: Optional[str] = None


@router.post("/call")
async def mcp_call(
    body: MCPCallRequest,
    wallet: Wallet = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    wrapper = _WRAPPERS.get(body.tool)
    if wrapper is None:
        raise HTTPException(status_code=400, detail={"error": "unknown_tool", "tool": body.tool})

    idempotency_key = body.idempotency_key or str(uuid.uuid4())
    metering = MeteringService(db)

    # PRE: balance check
    estimated_cost = await wrapper.estimate_cost(body.params)
    fee_pct = Decimal(str(settings.platform_fee_pct))
    estimated_total = estimated_cost * (1 + fee_pct)

    sufficient = await metering.check_balance(wallet.id, estimated_total)
    if not sufficient:
        raise HTTPException(
            status_code=402,
            detail={"error": "insufficient_balance", "required_usdt": str(estimated_total)},
        )

    # CALL upstream
    try:
        result, actual_cost = await wrapper.call(body.params)
        tx_status = TransactionStatus.completed
    except UpstreamError as exc:
        tx = await metering.debit(
            wallet_id=wallet.id,
            actual_cost=Decimal("0"),
            fee_pct=fee_pct,
            idempotency_key=idempotency_key,
            tool=body.tool,
            status=TransactionStatus.upstream_error,
            request_payload=body.params,
            response_meta={"error": str(exc), "status_code": exc.status_code},
        )
        raise HTTPException(
            status_code=502,
            detail={"error": "upstream_error", "message": str(exc), "transaction_id": str(tx.id)},
        )

    # POST: debit
    try:
        tx = await metering.debit(
            wallet_id=wallet.id,
            actual_cost=actual_cost,
            fee_pct=fee_pct,
            idempotency_key=idempotency_key,
            tool=body.tool,
            status=tx_status,
            request_payload=body.params,
            response_meta={"usage": result.get("usage")},
        )
    except InsufficientBalanceError:
        # Race condition: balance dropped between check and debit
        raise HTTPException(status_code=402, detail={"error": "insufficient_balance"})

    remaining = await metering.get_balance(wallet.id)

    return JSONResponse(
        content={
            "result": result,
            "transaction_id": str(tx.id),
            "cost_usdt": str(tx.upstream_cost),
            "fee_usdt": str(tx.fee_5pct),
            "total_usdt": str(tx.total_cost),
        },
        headers={"X-Balance-Remaining": str(remaining)},
    )
