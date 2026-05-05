from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.wrappers.openai_wrapper import OpenAIWrapper, _DEFAULT_MODEL, _token_cost
from src.wrappers.base import UpstreamError


def _make_response(input_tokens: int = 10, output_tokens: int = 5, model: str = _DEFAULT_MODEL):
    choice = MagicMock()
    choice.message.content = "Hello!"
    choice.finish_reason = "stop"

    resp = MagicMock()
    resp.id = "chatcmpl-001"
    resp.model = model
    resp.choices = [choice]
    resp.usage.prompt_tokens = input_tokens
    resp.usage.completion_tokens = output_tokens
    return resp


@pytest.mark.asyncio
async def test_estimate_cost_positive():
    wrapper = OpenAIWrapper()
    cost = await wrapper.estimate_cost(
        {"messages": [{"role": "user", "content": "Hello"}], "max_tokens": 100}
    )
    assert cost > Decimal("0")


@pytest.mark.asyncio
async def test_call_happy_path():
    wrapper = OpenAIWrapper()
    mock_resp = _make_response(input_tokens=10, output_tokens=5)

    with patch.object(
        wrapper._client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_resp
    ):
        result, cost = await wrapper.call(
            {"messages": [{"role": "user", "content": "Hello"}], "max_tokens": 10}
        )

    assert result["id"] == "chatcmpl-001"
    assert result["model"] == _DEFAULT_MODEL
    assert result["content"][0]["text"] == "Hello!"
    assert result["usage"]["input_tokens"] == 10
    assert result["usage"]["output_tokens"] == 5
    assert cost == _token_cost(10, 5)


@pytest.mark.asyncio
async def test_call_uses_default_model():
    wrapper = OpenAIWrapper()
    mock_resp = _make_response()

    with patch.object(
        wrapper._client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_resp
    ) as mock_create:
        await wrapper.call({"messages": [], "max_tokens": 1})

    assert mock_create.call_args.kwargs["model"] == _DEFAULT_MODEL


@pytest.mark.asyncio
async def test_call_api_status_error_raises_upstream_error():
    import openai as openai_lib

    wrapper = OpenAIWrapper()
    mock_http_resp = MagicMock()
    mock_http_resp.status_code = 429
    mock_http_resp.request = MagicMock()
    exc = openai_lib.APIStatusError("rate limited", response=mock_http_resp, body=None)

    with patch.object(
        wrapper._client.chat.completions, "create", new_callable=AsyncMock, side_effect=exc
    ):
        with pytest.raises(UpstreamError) as exc_info:
            await wrapper.call({"messages": [], "max_tokens": 1})

    assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_call_connection_error_raises_upstream_error():
    import openai as openai_lib

    wrapper = OpenAIWrapper()
    exc = openai_lib.APIConnectionError(request=MagicMock())

    with patch.object(
        wrapper._client.chat.completions, "create", new_callable=AsyncMock, side_effect=exc
    ):
        with pytest.raises(UpstreamError) as exc_info:
            await wrapper.call({"messages": [], "max_tokens": 1})

    assert exc_info.value.status_code == 0
