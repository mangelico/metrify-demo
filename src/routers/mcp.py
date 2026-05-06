import time
import uuid
from decimal import Decimal
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import require_api_key
from src.config import settings
from src.database import get_db
from src.limiter import limiter
from src.logging_config import get_logger
from src.models.transaction import TransactionStatus
from src.models.wallet import Wallet
from src.services.metering import InsufficientBalanceError, MeteringService
from src.wrappers.anthropic_wrapper import AnthropicWrapper
from src.wrappers.openai_wrapper import OpenAIWrapper
from src.wrappers.stability_wrapper import StabilityWrapper
from src.wrappers.assemblyai_wrapper import AssemblyAIWrapper
from src.wrappers.apify_wrapper import ApifyWrapper
from src.wrappers.firecrawl_wrapper import FirecrawlWrapper
from src.wrappers.base import UpstreamError

logger = get_logger("mcp")

router = APIRouter(prefix="/mcp", tags=["mcp"])

_WRAPPERS = {
    "anthropic": AnthropicWrapper(),
    "openai": OpenAIWrapper(),
    "stability": StabilityWrapper(),
    "assemblyai": AssemblyAIWrapper(),
    "apify": ApifyWrapper(),
    "firecrawl": FirecrawlWrapper(),
}


class MCPCallRequest(BaseModel):
    tool: str
    params: Dict[str, Any]
    idempotency_key: Optional[str] = None


def _rate_limit() -> str:
    return f"{settings.rate_limit_per_minute}/minute"


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", str(uuid.uuid4()))


@router.post("/call")
@limiter.limit(_rate_limit)
async def mcp_call(
    request: Request,
    body: MCPCallRequest,
    wallet: Wallet = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    request_id = _request_id(request)
    t0 = time.monotonic()

    wrapper = _WRAPPERS.get(body.tool)
    if wrapper is None:
        logger.warning(
            "tool_not_found",
            tool=body.tool,
            wallet_id=str(wallet.id),
            request_id=request_id,
        )
        raise HTTPException(
            status_code=404,
            detail={
                "error": "TOOL_NOT_FOUND",
                "message": f"Tool '{body.tool}' is not available.",
                "request_id": request_id,
                "available_tools": list(_WRAPPERS.keys()),
            },
        )

    idempotency_key = body.idempotency_key or str(uuid.uuid4())
    metering = MeteringService(db)

    # PRE: balance check
    estimated_cost = await wrapper.estimate_cost(body.params)
    fee_pct = Decimal(str(settings.platform_fee_pct))
    estimated_total = estimated_cost * (1 + fee_pct)

    sufficient = await metering.check_balance(wallet.id, estimated_total)
    if not sufficient:
        logger.warning(
            "insufficient_balance",
            tool=body.tool,
            wallet_id=str(wallet.id),
            estimated_cost=str(estimated_cost),
            request_id=request_id,
        )
        raise HTTPException(
            status_code=402,
            detail={
                "error": "INSUFFICIENT_BALANCE",
                "message": "Wallet balance is too low for this request.",
                "request_id": request_id,
                "required_usdt": str(estimated_total),
            },
        )

    # CALL upstream
    try:
        result, actual_cost = await wrapper.call(body.params)
        tx_status = TransactionStatus.completed
    except UpstreamError as exc:
        latency_ms = int((time.monotonic() - t0) * 1000)
        logger.error(
            "upstream_error",
            tool=body.tool,
            wallet_id=str(wallet.id),
            upstream_status_code=exc.status_code,
            latency_ms=latency_ms,
            request_id=request_id,
        )
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
            detail={
                "error": "UPSTREAM_ERROR",
                "message": str(exc),
                "request_id": request_id,
                "transaction_id": str(tx.id),
            },
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
        raise HTTPException(
            status_code=402,
            detail={
                "error": "INSUFFICIENT_BALANCE",
                "message": "Wallet balance is too low after actual cost was computed.",
                "request_id": request_id,
            },
        )

    remaining = await metering.get_balance(wallet.id)
    latency_ms = int((time.monotonic() - t0) * 1000)

    logger.info(
        "tool_call_completed",
        tool=body.tool,
        wallet_id=str(wallet.id),
        cost_usdt=str(actual_cost),
        total_usdt=str(tx.total_cost),
        status="completed",
        latency_ms=latency_ms,
        request_id=request_id,
    )

    return JSONResponse(
        content={
            "result": result,
            "transaction_id": str(tx.id),
            "cost_usdt": str(tx.upstream_cost),
            "fee_usdt": str(tx.fee_5pct),
            "total_usdt": str(tx.total_cost),
            "request_id": request_id,
        },
        headers={"X-Balance-Remaining": str(remaining)},
    )
