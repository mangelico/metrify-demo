from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, call, patch

import httpx
import pytest

from src.wrappers.apify_wrapper import ApifyWrapper
from src.wrappers.base import UpstreamError


def _make_run_response(run_id: str = "run123") -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = {"data": {"id": run_id}}
    resp.raise_for_status = MagicMock()
    resp.status_code = 201
    return resp


def _make_status_response(status: str) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = {"data": {"id": "run123", "status": status}}
    resp.raise_for_status = MagicMock()
    resp.status_code = 200
    return resp


def _make_output_response(items: list) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = items
    resp.raise_for_status = MagicMock()
    resp.status_code = 200
    return resp


@pytest.mark.asyncio
async def test_estimate_cost():
    wrapper = ApifyWrapper()
    cost = await wrapper.estimate_cost({})
    assert cost == Decimal("0.005")


@pytest.mark.asyncio
async def test_estimate_cost_ignores_params():
    wrapper = ApifyWrapper()
    cost = await wrapper.estimate_cost({"actor_id": "some/actor", "input": {"url": "x"}})
    assert cost == Decimal("0.005")


@pytest.mark.asyncio
async def test_call_happy_path_succeeded():
    wrapper = ApifyWrapper()

    run_resp = _make_run_response("run123")
    status_resp = _make_status_response("SUCCEEDED")
    output_resp = _make_output_response([{"title": "Example"}])

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=run_resp)
    mock_client.get = AsyncMock(side_effect=[status_resp, output_resp])

    with patch("src.wrappers.apify_wrapper.httpx.AsyncClient", return_value=mock_client):
        result, cost = await wrapper.call({
            "actor_id": "apify/cheerio-scraper",
            "input": {"startUrls": [{"url": "https://example.com"}]},
        })

    assert result["status"] == "SUCCEEDED"
    assert result["run_id"] == "run123"
    assert result["output"]["items"] == [{"title": "Example"}]
    assert cost == Decimal("0.005")


@pytest.mark.asyncio
async def test_call_run_failed_raises_upstream_error():
    wrapper = ApifyWrapper()

    run_resp = _make_run_response("run456")
    fail_resp = _make_status_response("FAILED")

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=run_resp)
    mock_client.get = AsyncMock(return_value=fail_resp)

    with patch("src.wrappers.apify_wrapper.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(UpstreamError) as exc_info:
            await wrapper.call({"actor_id": "apify/cheerio-scraper", "input": {}})

    assert "run456" in str(exc_info.value)
    assert exc_info.value.status_code == 0


@pytest.mark.asyncio
async def test_call_timeout_returns_pending_no_charge():
    wrapper = ApifyWrapper()

    run_resp = _make_run_response("run789")
    running_resp = _make_status_response("RUNNING")

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=run_resp)
    mock_client.get = AsyncMock(return_value=running_resp)

    with patch("src.wrappers.apify_wrapper.httpx.AsyncClient", return_value=mock_client):
        with patch("src.wrappers.apify_wrapper._POLL_TIMEOUT_SECONDS", 0):
            result, cost = await wrapper.call({"actor_id": "apify/test", "input": {}})

    assert result["status"] == "pending"
    assert result["run_id"] == "run789"
    assert cost == Decimal("0")


@pytest.mark.asyncio
async def test_call_http_status_error_raises_upstream_error():
    wrapper = ApifyWrapper()
    mock_bad_resp = MagicMock()
    mock_bad_resp.status_code = 401
    mock_bad_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Unauthorized", request=MagicMock(), response=mock_bad_resp
    )

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_bad_resp)

    with patch("src.wrappers.apify_wrapper.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(UpstreamError) as exc_info:
            await wrapper.call({"actor_id": "apify/test", "input": {}})

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_call_request_error_raises_upstream_error():
    wrapper = ApifyWrapper()
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(
        side_effect=httpx.RequestError("Connection refused", request=MagicMock())
    )

    with patch("src.wrappers.apify_wrapper.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(UpstreamError) as exc_info:
            await wrapper.call({"actor_id": "apify/test", "input": {}})

    assert exc_info.value.status_code == 0


@pytest.mark.asyncio
async def test_call_polls_until_succeeded():
    wrapper = ApifyWrapper()

    run_resp = _make_run_response("runABC")
    running_resp = _make_status_response("RUNNING")
    succeeded_resp = _make_status_response("SUCCEEDED")
    output_resp = _make_output_response([{"result": "done"}])

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=run_resp)
    mock_client.get = AsyncMock(side_effect=[running_resp, succeeded_resp, output_resp])

    with patch("src.wrappers.apify_wrapper.httpx.AsyncClient", return_value=mock_client):
        with patch("src.wrappers.apify_wrapper.asyncio.sleep", return_value=None):
            result, cost = await wrapper.call({"actor_id": "apify/test", "input": {}})

    assert result["status"] == "SUCCEEDED"
    assert cost == Decimal("0.005")
