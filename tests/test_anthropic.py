import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from metrify import InsufficientBalanceError, GatewayError
from metrify.exceptions import UpstreamError


@pytest.fixture
def anthropic_fn(mock_server, mock_m):
    from tools.anthropic_tool import register
    return register(mock_server, mock_m)


async def test_anthropic_happy_path(anthropic_fn, mock_m, with_ck):
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Generated text")]

    with patch("anthropic.AsyncAnthropic") as mock_cls:
        mock_cls.return_value.messages.create = AsyncMock(return_value=mock_response)
        result = await anthropic_fn("Hello!")

    assert result == "Generated text"
    mock_m._billing.check_balance.assert_called_once_with(consumer_api_key="ck_test", required=0.000065)
    mock_m._billing.charge.assert_called_once_with(consumer_api_key="ck_test", tool_name="anthropic", cost=0.000065)


async def test_anthropic_insufficient_balance(anthropic_fn, mock_m, with_ck):
    mock_m._billing.check_balance.side_effect = InsufficientBalanceError("no funds")

    with pytest.raises(InsufficientBalanceError):
        await anthropic_fn("Hello!")

    mock_m._billing.charge.assert_not_called()


async def test_anthropic_gateway_error(anthropic_fn, mock_m, with_ck):
    mock_m._billing.check_balance.side_effect = GatewayError("timeout")

    with pytest.raises(GatewayError):
        await anthropic_fn("Hello!")

    mock_m._billing.charge.assert_not_called()


async def test_anthropic_api_failure_no_charge(anthropic_fn, mock_m, with_ck):
    with patch("anthropic.AsyncAnthropic") as mock_cls:
        mock_cls.return_value.messages.create = AsyncMock(
            side_effect=Exception("Anthropic 500")
        )
        result = await anthropic_fn("Hello!")

    assert result.startswith("Error:")
    mock_m._billing.charge.assert_not_called()


async def test_anthropic_prompt_too_long(anthropic_fn, mock_m, with_ck):
    long_prompt = "x" * 2001
    result = await anthropic_fn(long_prompt)
    assert result.startswith("Error:")
    assert "2000" in result
    mock_m._billing.charge.assert_not_called()


async def test_anthropic_max_tokens_capped(anthropic_fn, mock_m, with_ck):
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="response")]

    with patch("anthropic.AsyncAnthropic") as mock_cls:
        mock_cls.return_value.messages.create = AsyncMock(return_value=mock_response)
        result = await anthropic_fn("Hello!", max_tokens=1000)

    assert result == "response"
    call_kwargs = mock_cls.return_value.messages.create.call_args.kwargs
    assert call_kwargs["max_tokens"] == 512
    mock_m._billing.charge.assert_called_once()
