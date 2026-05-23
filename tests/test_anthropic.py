import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from metrify import InsufficientBalanceError, GatewayError


@pytest.fixture
def anthropic_fn(mock_server, mock_m):
    from tools.anthropic_tool import register
    return register(mock_server, mock_m)


async def test_anthropic_happy_path(anthropic_fn, mock_m):
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Generated text")]

    with patch("anthropic.AsyncAnthropic") as mock_cls:
        mock_cls.return_value.messages.create = AsyncMock(return_value=mock_response)
        result = await anthropic_fn("ck_test", "Hello!")

    assert result == "Generated text"
    mock_m._billing.check_balance.assert_called_once_with(consumer_api_key="ck_test", required=0.000065)
    mock_m._billing.charge.assert_called_once_with(consumer_api_key="ck_test", tool_name="anthropic", cost=0.000065)


async def test_anthropic_insufficient_balance(anthropic_fn, mock_m):
    mock_m._billing.check_balance.side_effect = InsufficientBalanceError("no funds")

    with pytest.raises(InsufficientBalanceError):
        await anthropic_fn("ck_test", "Hello!")

    mock_m._billing.charge.assert_not_called()


async def test_anthropic_gateway_error(anthropic_fn, mock_m):
    mock_m._billing.check_balance.side_effect = GatewayError("timeout")

    with pytest.raises(GatewayError):
        await anthropic_fn("ck_test", "Hello!")

    mock_m._billing.charge.assert_not_called()


async def test_anthropic_api_failure_no_charge(anthropic_fn, mock_m):
    with patch("anthropic.AsyncAnthropic") as mock_cls:
        mock_cls.return_value.messages.create = AsyncMock(
            side_effect=Exception("Anthropic 500")
        )
        result = await anthropic_fn("ck_test", "Hello!")

    assert result.startswith("Error:")
    mock_m._billing.charge.assert_not_called()
