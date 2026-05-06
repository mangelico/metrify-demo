from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.wrappers.firecrawl_wrapper import FirecrawlWrapper
from src.wrappers.base import UpstreamError


def _make_mock_client(response_json: dict, status_code: int = 200):
    mock_response = MagicMock()
    mock_response.json.return_value = response_json
    mock_response.raise_for_status = MagicMock()
    mock_response.status_code = status_code

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.get = AsyncMock(return_value=mock_response)
    return mock_client


@pytest.mark.asyncio
async def test_estimate_cost():
    wrapper = FirecrawlWrapper()
    cost = await wrapper.estimate_cost({})
    assert cost == Decimal("0.001")


@pytest.mark.asyncio
async def test_estimate_cost_ignores_params():
    wrapper = FirecrawlWrapper()
    cost = await wrapper.estimate_cost({"url": "https://example.com"})
    assert cost == Decimal("0.001")


@pytest.mark.asyncio
async def test_call_happy_path():
    wrapper = FirecrawlWrapper()
    mock_client = _make_mock_client({
        "success": True,
        "data": {
            "markdown": "# Example\n\nThis is example content.",
            "metadata": {"title": "Example Domain", "sourceURL": "https://example.com"},
        },
    })

    with patch("src.wrappers.firecrawl_wrapper.httpx.AsyncClient", return_value=mock_client):
        result, cost = await wrapper.call({"url": "https://example.com"})

    assert cost == Decimal("0.001")
    assert result["url"] == "https://example.com"
    assert "# Example" in result["markdown"]
    assert result["metadata"]["title"] == "Example Domain"
    assert result["usage"]["pages"] == 1


@pytest.mark.asyncio
async def test_call_success_false_raises_upstream_error():
    wrapper = FirecrawlWrapper()
    mock_client = _make_mock_client({
        "success": False,
        "error": "URL not accessible",
    })

    with patch("src.wrappers.firecrawl_wrapper.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(UpstreamError) as exc_info:
            await wrapper.call({"url": "https://blocked-url.com"})

    assert "URL not accessible" in str(exc_info.value)


@pytest.mark.asyncio
async def test_call_http_status_error_raises_upstream_error():
    wrapper = FirecrawlWrapper()
    mock_bad_resp = MagicMock()
    mock_bad_resp.status_code = 429
    mock_bad_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Rate limit exceeded", request=MagicMock(), response=mock_bad_resp
    )

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_bad_resp)

    with patch("src.wrappers.firecrawl_wrapper.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(UpstreamError) as exc_info:
            await wrapper.call({"url": "https://example.com"})

    assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_call_request_error_raises_upstream_error():
    wrapper = FirecrawlWrapper()
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(
        side_effect=httpx.RequestError("Connection refused", request=MagicMock())
    )

    with patch("src.wrappers.firecrawl_wrapper.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(UpstreamError) as exc_info:
            await wrapper.call({"url": "https://example.com"})

    assert exc_info.value.status_code == 0


@pytest.mark.asyncio
async def test_call_returns_markdown_content():
    wrapper = FirecrawlWrapper()
    expected_markdown = "# Title\n\nParagraph with **bold** text.\n\n- item 1\n- item 2"
    mock_client = _make_mock_client({
        "success": True,
        "data": {
            "markdown": expected_markdown,
            "metadata": {},
        },
    })

    with patch("src.wrappers.firecrawl_wrapper.httpx.AsyncClient", return_value=mock_client):
        result, cost = await wrapper.call({"url": "https://example.com"})

    assert result["markdown"] == expected_markdown
