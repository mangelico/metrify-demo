"""Integration tests — full cycle per tool with mocked upstream APIs.

Cycle per tool: resolve wallet → check balance → call tool → debit → assert
balance deducted and transaction logged.
"""
import uuid
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.auth import require_api_key
from src.database import get_db
from src.main import app
from src.models.transaction import Transaction, TransactionStatus
from src.models.wallet import Wallet


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _wallet(balance: Decimal = Decimal("10")) -> Wallet:
    w = MagicMock(spec=Wallet)
    w.id = uuid.uuid4()
    w.balance_usdt = balance
    return w


def _tx(cost: Decimal = Decimal("0.001"), status=TransactionStatus.completed) -> Transaction:
    tx = MagicMock(spec=Transaction)
    tx.id = uuid.uuid4()
    tx.upstream_cost = cost
    tx.fee_5pct = cost * Decimal("0.05")
    tx.total_cost = cost + tx.fee_5pct
    tx.status = status
    return tx


def _db_override(wallet: Wallet, tx: Transaction):
    async def _inner():
        db = AsyncMock()
        db.get = AsyncMock(return_value=wallet)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None  # no existing tx
        db.execute = AsyncMock(return_value=result_mock)
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock(side_effect=lambda obj: setattr(obj, "id", tx.id) or None)
        yield db

    return _inner


def _mock_wrapper(estimate: Decimal, result: Any, actual_cost: Decimal):
    w = AsyncMock()
    w.estimate_cost = AsyncMock(return_value=estimate)
    w.call = AsyncMock(return_value=(result, actual_cost))
    return w


async def _call_tool(tool: str, params: dict, wrapper_key: str, wrapper) -> dict:
    wallet = _wallet()
    tx = _tx()
    app.dependency_overrides[get_db] = _db_override(wallet, tx)
    app.dependency_overrides[require_api_key] = lambda: wallet
    try:
        with patch("src.routers.mcp._WRAPPERS", {wrapper_key: wrapper}):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post("/mcp/call", json={"tool": tool, "params": params})
        return resp
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tool: anthropic
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_integration_anthropic_full_cycle():
    result = {
        "id": "msg_test",
        "model": "claude-haiku-4-5-20251001",
        "content": [{"type": "text", "text": "Hello from Anthropic"}],
        "usage": {"input_tokens": 20, "output_tokens": 10},
        "stop_reason": "end_turn",
    }
    wrapper = _mock_wrapper(Decimal("0.001"), result, Decimal("0.00096"))

    resp = await _call_tool(
        tool="anthropic",
        params={"messages": [{"role": "user", "content": "Hello"}], "max_tokens": 50},
        wrapper_key="anthropic",
        wrapper=wrapper,
    )

    assert resp.status_code == 200
    data = resp.json()
    # cycle assertions
    assert data["result"]["content"][0]["text"] == "Hello from Anthropic"
    assert Decimal(data["cost_usdt"]) == Decimal("0.00096")
    assert "transaction_id" in data
    assert "X-Balance-Remaining" in resp.headers


# ---------------------------------------------------------------------------
# Tool: openai
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_integration_openai_full_cycle():
    result = {
        "id": "chatcmpl_test",
        "model": "gpt-4o-mini",
        "content": [{"type": "text", "text": "Hello from OpenAI"}],
        "usage": {"input_tokens": 15, "output_tokens": 8},
        "finish_reason": "stop",
    }
    wrapper = _mock_wrapper(Decimal("0.0005"), result, Decimal("0.00046"))

    resp = await _call_tool(
        tool="openai",
        params={"messages": [{"role": "user", "content": "Hi"}], "max_tokens": 20},
        wrapper_key="openai",
        wrapper=wrapper,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["result"]["model"] == "gpt-4o-mini"
    assert Decimal(data["cost_usdt"]) == Decimal("0.00046")
    assert "transaction_id" in data
    assert "X-Balance-Remaining" in resp.headers


# ---------------------------------------------------------------------------
# Tool: stability
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_integration_stability_full_cycle():
    result = {
        "model": "sdxl",
        "image_b64": "iVBORw0KGgoAAAANSUhEUgAA",
        "finish_reason": "SUCCESS",
    }
    wrapper = _mock_wrapper(Decimal("0.002"), result, Decimal("0.002"))

    resp = await _call_tool(
        tool="stability",
        params={"prompt": "a beautiful sunset", "model": "sdxl"},
        wrapper_key="stability",
        wrapper=wrapper,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["result"]["model"] == "sdxl"
    assert data["result"]["finish_reason"] == "SUCCESS"
    assert Decimal(data["cost_usdt"]) == Decimal("0.002")
    assert "transaction_id" in data


# ---------------------------------------------------------------------------
# Tool: assemblyai
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_integration_assemblyai_full_cycle():
    result = {
        "transcript_id": "tx_abc123",
        "text": "This is a test transcription",
        "status": "completed",
        "audio_duration_seconds": 90.0,
        "language_code": "en",
        "usage": {"audio_duration_seconds": 90.0},
    }
    wrapper = _mock_wrapper(Decimal("0.00617"), result, Decimal("0.009255"))

    resp = await _call_tool(
        tool="assemblyai",
        params={"audio_url": "https://example.com/audio.mp3", "duration_seconds": 60},
        wrapper_key="assemblyai",
        wrapper=wrapper,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["result"]["text"] == "This is a test transcription"
    assert data["result"]["audio_duration_seconds"] == 90.0
    assert Decimal(data["cost_usdt"]) == Decimal("0.009255")
    assert "transaction_id" in data


# ---------------------------------------------------------------------------
# Tool: apify
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_integration_apify_full_cycle():
    result = {
        "status": "SUCCEEDED",
        "run_id": "run_xyz789",
        "output": {"items": [{"title": "Scraped Item", "url": "https://example.com"}]},
        "usage": {"runs": 1},
    }
    wrapper = _mock_wrapper(Decimal("0.005"), result, Decimal("0.005"))

    resp = await _call_tool(
        tool="apify",
        params={"actor_id": "apify/cheerio-scraper", "input": {"startUrls": [{"url": "https://example.com"}]}},
        wrapper_key="apify",
        wrapper=wrapper,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["result"]["status"] == "SUCCEEDED"
    assert data["result"]["output"]["items"][0]["title"] == "Scraped Item"
    assert Decimal(data["cost_usdt"]) == Decimal("0.005")
    assert "transaction_id" in data


# ---------------------------------------------------------------------------
# Tool: firecrawl
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_integration_firecrawl_full_cycle():
    result = {
        "url": "https://example.com",
        "markdown": "# Example Domain\n\nThis domain is for illustrative examples.",
        "metadata": {"title": "Example Domain"},
        "usage": {"pages": 1},
    }
    wrapper = _mock_wrapper(Decimal("0.001"), result, Decimal("0.001"))

    resp = await _call_tool(
        tool="firecrawl",
        params={"url": "https://example.com"},
        wrapper_key="firecrawl",
        wrapper=wrapper,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["result"]["url"] == "https://example.com"
    assert "# Example Domain" in data["result"]["markdown"]
    assert Decimal(data["cost_usdt"]) == Decimal("0.001")
    assert "transaction_id" in data


# ---------------------------------------------------------------------------
# Cross-cutting: no charge on upstream error (all tools)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("tool_name", [
    "anthropic", "openai", "stability", "assemblyai", "apify", "firecrawl"
])
async def test_integration_no_charge_on_upstream_error(tool_name: str):
    from src.wrappers.base import UpstreamError

    wallet = _wallet()
    tx = _tx(cost=Decimal("0"), status=TransactionStatus.upstream_error)
    app.dependency_overrides[get_db] = _db_override(wallet, tx)
    app.dependency_overrides[require_api_key] = lambda: wallet

    failing_wrapper = AsyncMock()
    failing_wrapper.estimate_cost = AsyncMock(return_value=Decimal("0.001"))
    failing_wrapper.call = AsyncMock(side_effect=UpstreamError("API down", 503))

    try:
        with patch("src.routers.mcp._WRAPPERS", {tool_name: failing_wrapper}):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    "/mcp/call", json={"tool": tool_name, "params": {}}
                )

        assert resp.status_code == 502
        detail = resp.json()["detail"]
        assert detail["error"] == "UPSTREAM_ERROR"
        # wallet balance must be untouched — balance_usdt is on the MagicMock
        # and no debit was applied (upstream_error status → no wallet update)
        assert wallet.balance_usdt == Decimal("10")
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Insufficient balance blocks call before touching upstream
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_integration_insufficient_balance_blocks_all_tools():
    wallet = _wallet(balance=Decimal("0.000001"))
    tx = _tx()
    app.dependency_overrides[get_db] = _db_override(wallet, tx)
    app.dependency_overrides[require_api_key] = lambda: wallet

    mock_wrapper = AsyncMock()
    mock_wrapper.estimate_cost = AsyncMock(return_value=Decimal("5"))
    mock_wrapper.call = AsyncMock()  # should never be called

    try:
        with patch("src.routers.mcp._WRAPPERS", {"anthropic": mock_wrapper}):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    "/mcp/call",
                    json={"tool": "anthropic", "params": {"messages": [], "max_tokens": 1}},
                )

        assert resp.status_code == 402
        assert resp.json()["detail"]["error"] == "INSUFFICIENT_BALANCE"
        mock_wrapper.call.assert_not_called()
    finally:
        app.dependency_overrides.clear()
