import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from metrify import InsufficientBalanceError, GatewayError


@pytest.fixture
def openai_fn(mock_server, mock_m):
    from tools.openai_tool import register
    return register(mock_server, mock_m)


async def test_openai_happy_path(openai_fn, mock_m):
    mock_message = MagicMock()
    mock_message.message.content = "GPT response"
    mock_response = MagicMock()
    mock_response.choices = [mock_message]

    with patch("openai.AsyncOpenAI") as mock_cls:
        mock_cls.return_value.chat.completions.create = AsyncMock(return_value=mock_response)
        result = await openai_fn("ck_test", "Hello!")

    assert result == "GPT response"
    mock_m._billing.check_balance.assert_called_once_with(consumer_api_key="ck_test", required=0.000010)
    mock_m._billing.charge.assert_called_once_with(consumer_api_key="ck_test", tool_name="openai", cost=0.000010)


async def test_openai_insufficient_balance(openai_fn, mock_m):
    mock_m._billing.check_balance.side_effect = InsufficientBalanceError("no funds")

    with pytest.raises(InsufficientBalanceError):
        await openai_fn("ck_test", "Hello!")

    mock_m._billing.charge.assert_not_called()


async def test_openai_gateway_error(openai_fn, mock_m):
    mock_m._billing.check_balance.side_effect = GatewayError("timeout")

    with pytest.raises(GatewayError):
        await openai_fn("ck_test", "Hello!")

    mock_m._billing.charge.assert_not_called()


async def test_openai_api_failure_no_charge(openai_fn, mock_m):
    with patch("openai.AsyncOpenAI") as mock_cls:
        mock_cls.return_value.chat.completions.create = AsyncMock(
            side_effect=Exception("OpenAI 429")
        )
        result = await openai_fn("ck_test", "Hello!")

    assert result.startswith("Error:")
    mock_m._billing.charge.assert_not_called()
