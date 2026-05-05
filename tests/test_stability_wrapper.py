from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.wrappers.stability_wrapper import StabilityWrapper
from src.wrappers.base import UpstreamError


def _make_mock_client(response_json: dict):
    mock_response = MagicMock()
    mock_response.json.return_value = response_json
    mock_response.raise_for_status = MagicMock()
    mock_response.status_code = 200

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.get = AsyncMock(return_value=mock_response)
    return mock_client


@pytest.mark.asyncio
async def test_estimate_cost_sdxl():
    wrapper = StabilityWrapper()
    cost = await wrapper.estimate_cost({"model": "sdxl"})
    assert cost == Decimal("0.002")


@pytest.mark.asyncio
async def test_estimate_cost_sd3():
    wrapper = StabilityWrapper()
    cost = await wrapper.estimate_cost({"model": "sd3"})
    assert cost == Decimal("0.035")


@pytest.mark.asyncio
async def test_estimate_cost_default_is_sdxl():
    wrapper = StabilityWrapper()
    cost = await wrapper.estimate_cost({})
    assert cost == Decimal("0.002")


@pytest.mark.asyncio
async def test_call_sdxl_happy_path():
    wrapper = StabilityWrapper()
    mock_client = _make_mock_client(
        {"artifacts": [{"base64": "abc123", "finishReason": "SUCCESS"}]}
    )

    with patch("src.wrappers.stability_wrapper.httpx.AsyncClient", return_value=mock_client):
        result, cost = await wrapper.call({"model": "sdxl", "prompt": "a cat"})

    assert cost == Decimal("0.002")
    assert result["model"] == "sdxl"
    assert result["image_b64"] == "abc123"
    assert result["finish_reason"] == "SUCCESS"


@pytest.mark.asyncio
async def test_call_sd3_happy_path():
    wrapper = StabilityWrapper()
    mock_client = _make_mock_client({"image": "def456", "finish_reason": "SUCCESS"})

    with patch("src.wrappers.stability_wrapper.httpx.AsyncClient", return_value=mock_client):
        result, cost = await wrapper.call({"model": "sd3", "prompt": "a dog"})

    assert cost == Decimal("0.035")
    assert result["model"] == "sd3"
    assert result["image_b64"] == "def456"


@pytest.mark.asyncio
async def test_call_default_model_is_sdxl():
    wrapper = StabilityWrapper()
    mock_client = _make_mock_client(
        {"artifacts": [{"base64": "xyz", "finishReason": "SUCCESS"}]}
    )

    with patch("src.wrappers.stability_wrapper.httpx.AsyncClient", return_value=mock_client):
        result, cost = await wrapper.call({"prompt": "no model specified"})

    assert result["model"] == "sdxl"
    assert cost == Decimal("0.002")


@pytest.mark.asyncio
async def test_call_upstream_http_error_raises_and_no_charge():
    wrapper = StabilityWrapper()

    mock_bad_response = MagicMock()
    mock_bad_response.status_code = 500
    mock_bad_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Server Error", request=MagicMock(), response=mock_bad_response
    )

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_bad_response)

    with patch("src.wrappers.stability_wrapper.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(UpstreamError) as exc_info:
            await wrapper.call({"model": "sdxl", "prompt": "a cat"})

    assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_call_request_error_raises():
    wrapper = StabilityWrapper()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(
        side_effect=httpx.RequestError("timeout", request=MagicMock())
    )

    with patch("src.wrappers.stability_wrapper.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(UpstreamError) as exc_info:
            await wrapper.call({"model": "sdxl", "prompt": "a cat"})

    assert exc_info.value.status_code == 0
