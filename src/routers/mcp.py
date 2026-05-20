import json
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


def _rate_limit() -> str:
    return f"{settings.rate_limit_per_minute}/minute"


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", str(uuid.uuid4()))


# ---------------------------------------------------------------------------
# MCP Protocol — tool schemas (tools/list)
# ---------------------------------------------------------------------------

_TOOL_SCHEMAS = [
    {
        "name": "anthropic",
        "description": (
            "Call Anthropic Claude (haiku-4-5) LLM. Billed per token. "
            "Pricing: $0.80/M input, $4.00/M output + 5% platform fee."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "messages": {
                    "type": "array",
                    "description": "Conversation messages [{role, content}]",
                    "items": {"type": "object"},
                },
                "max_tokens": {"type": "integer", "description": "Max output tokens", "default": 1024},
                "model": {"type": "string", "description": "Model ID (default: claude-haiku-4-5-20251001)"},
                "system": {"type": "string", "description": "System prompt"},
            },
            "required": ["messages"],
        },
    },
    {
        "name": "openai",
        "description": (
            "Call OpenAI GPT-4o-mini LLM. Billed per token. "
            "Pricing: $0.15/M input, $0.60/M output + 5% platform fee."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "messages": {
                    "type": "array",
                    "description": "Conversation messages [{role, content}]",
                    "items": {"type": "object"},
                },
                "max_tokens": {"type": "integer", "default": 1024},
                "model": {"type": "string", "default": "gpt-4o-mini"},
                "temperature": {"type": "number", "default": 1.0},
            },
            "required": ["messages"],
        },
    },
    {
        "name": "stability",
        "description": (
            "Generate images with Stability AI. Billed per image. "
            "Pricing: $0.002 (sdxl) or $0.035 (sd3) + 5% platform fee."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Image generation prompt"},
                "model": {"type": "string", "description": "sdxl or sd3", "default": "sdxl"},
                "output_format": {"type": "string", "default": "png"},
            },
            "required": ["prompt"],
        },
    },
    {
        "name": "assemblyai",
        "description": (
            "Transcribe audio with AssemblyAI. Billed per minute of audio. "
            "Pricing: $0.00617/min + 5% platform fee."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "audio_url": {"type": "string", "description": "URL of audio file to transcribe"},
                "language_code": {"type": "string", "default": "en"},
            },
            "required": ["audio_url"],
        },
    },
    {
        "name": "apify",
        "description": (
            "Run Apify web automation actors asynchronously. Billed per run. "
            "Pricing: $0.005/run + 5% platform fee."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "actor_id": {"type": "string", "description": "Apify actor ID (e.g. apify/web-scraper)"},
                "run_input": {"type": "object", "description": "Input JSON for the actor", "default": {}},
                "timeout_secs": {"type": "integer", "description": "Max run time in seconds", "default": 300},
            },
            "required": ["actor_id"],
        },
    },
    {
        "name": "firecrawl",
        "description": (
            "Scrape web pages and extract content with Firecrawl. Billed per page. "
            "Pricing: $0.001/page + 5% platform fee."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to scrape"},
                "formats": {
                    "type": "array",
                    "description": "Output formats: markdown, html, rawHtml, links, screenshot",
                    "items": {"type": "string"},
                    "default": ["markdown"],
                },
            },
            "required": ["url"],
        },
    },
]


# ---------------------------------------------------------------------------
# JSON-RPC helpers
# ---------------------------------------------------------------------------

def _jsonrpc_result(rpc_id: Any, result: Any) -> JSONResponse:
    return JSONResponse(content={"jsonrpc": "2.0", "id": rpc_id, "result": result})


def _jsonrpc_error(rpc_id: Any, code: int, message: str) -> JSONResponse:
    return JSONResponse(
        content={"jsonrpc": "2.0", "id": rpc_id, "error": {"code": code, "message": message}}
    )


# ---------------------------------------------------------------------------
# MCP Streamable HTTP transport — POST /mcp
# ---------------------------------------------------------------------------

@router.post("")
@limiter.limit(_rate_limit)
async def mcp_protocol(
    request: Request,
    wallet: Wallet = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Standard MCP Streamable HTTP endpoint (initialize / tools/list / tools/call)."""
    try:
        body = await request.json()
    except Exception:
        return _jsonrpc_error(None, -32700, "Parse error")

    # JSON-RPC notifications have no "id" field — must not send a response
    if "id" not in body:
        return JSONResponse(content={})

    rpc_id = body.get("id")
    method = body.get("method", "")
    params = body.get("params") or {}

    if method == "initialize":
        return _jsonrpc_result(
            rpc_id,
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "modelo-gateway", "version": "0.1.0"},
            },
        )

    if method == "tools/list":
        return _jsonrpc_result(rpc_id, {"tools": _TOOL_SCHEMAS})

    if method == "tools/call":
        return await _handle_mcp_tools_call(rpc_id, params, wallet, db, request)

    return _jsonrpc_error(rpc_id, -32601, f"Method not found: {method}")


async def _handle_mcp_tools_call(
    rpc_id: Any,
    params: dict,
    wallet: Wallet,
    db: AsyncSession,
    request: Request,
) -> JSONResponse:
    """Execute a tool via the standard MCP tools/call method with full billing."""
    request_id = _request_id(request)
    t0 = time.monotonic()

    tool_name = params.get("name")
    arguments = params.get("arguments") or {}

    wrapper = _WRAPPERS.get(tool_name)
    if wrapper is None:
        return _jsonrpc_error(
            rpc_id,
            -32602,
            f"Tool '{tool_name}' not found. Available: {list(_WRAPPERS.keys())}",
        )

    idempotency_key = str(uuid.uuid4())
    metering = MeteringService(db)
    fee_pct = Decimal(str(settings.platform_fee_pct))

    estimated_cost = await wrapper.estimate_cost(arguments)
    estimated_total = estimated_cost * (1 + fee_pct)

    sufficient = await metering.check_balance(wallet.id, estimated_total)
    if not sufficient:
        logger.warning(
            "mcp_insufficient_balance",
            tool=tool_name,
            wallet_id=str(wallet.id),
            request_id=request_id,
        )
        return _jsonrpc_result(
            rpc_id,
            {
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"Insufficient balance. "
                            f"Required: {estimated_total:.6f} USDT. "
                            f"Top up at /dashboard or POST /wallets/{{id}}/topup"
                        ),
                    }
                ],
                "isError": True,
            },
        )

    try:
        result, actual_cost = await wrapper.call(arguments)
        tx_status = TransactionStatus.completed
    except UpstreamError as exc:
        latency_ms = int((time.monotonic() - t0) * 1000)
        logger.error(
            "mcp_upstream_error",
            tool=tool_name,
            wallet_id=str(wallet.id),
            upstream_status_code=exc.status_code,
            latency_ms=latency_ms,
            request_id=request_id,
        )
        await metering.debit(
            wallet_id=wallet.id,
            actual_cost=Decimal("0"),
            fee_pct=fee_pct,
            idempotency_key=idempotency_key,
            tool=tool_name,
            status=TransactionStatus.upstream_error,
            request_payload=arguments,
            response_meta={"error": str(exc), "status_code": exc.status_code},
        )
        return _jsonrpc_result(
            rpc_id,
            {
                "content": [{"type": "text", "text": f"Upstream error: {exc}"}],
                "isError": True,
            },
        )

    try:
        tx = await metering.debit(
            wallet_id=wallet.id,
            actual_cost=actual_cost,
            fee_pct=fee_pct,
            idempotency_key=idempotency_key,
            tool=tool_name,
            status=tx_status,
            request_payload=arguments,
            response_meta={"usage": result.get("usage")},
        )
    except InsufficientBalanceError:
        return _jsonrpc_result(
            rpc_id,
            {
                "content": [{"type": "text", "text": "Debit failed: balance insufficient after call."}],
                "isError": True,
            },
        )

    remaining = await metering.get_balance(wallet.id)
    latency_ms = int((time.monotonic() - t0) * 1000)

    logger.info(
        "mcp_tool_call_completed",
        tool=tool_name,
        wallet_id=str(wallet.id),
        cost_usdt=str(actual_cost),
        total_usdt=str(tx.total_cost),
        latency_ms=latency_ms,
        request_id=request_id,
    )

    return _jsonrpc_result(
        rpc_id,
        {
            "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
            "_meta": {
                "transaction_id": str(tx.id),
                "cost_usdt": str(tx.upstream_cost),
                "fee_usdt": str(tx.fee_5pct),
                "total_usdt": str(tx.total_cost),
                "balance_remaining": str(remaining),
            },
        },
    )


# ---------------------------------------------------------------------------
# Legacy HTTP API — POST /mcp/call  (kept for backwards compatibility)
# ---------------------------------------------------------------------------

class MCPCallRequest(BaseModel):
    tool: str
    params: Dict[str, Any]
    idempotency_key: Optional[str] = None


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
