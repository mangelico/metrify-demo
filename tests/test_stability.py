import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from metrify import InsufficientBalanceError, GatewayError


@pytest.fixture
def stability_fn(mock_server, mock_m):
    from tools.stability_tool import register
    return register(mock_server, mock_m)


async def test_stability_happy_path(stability_fn, mock_m):
    mock_response = MagicMock()
    mock_response.json.return_value = {"artifacts": [{"base64": "abc123=="}]}
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_cls.return_value)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value.post = AsyncMock(return_value=mock_response)
        result = await stability_fn("a sunset over the ocean", consumer_api_key="ck_test")

    assert result == "abc123=="
    mock_m._billing.check_balance.assert_called_once_with(consumer_api_key="ck_test", required=0.002)
    mock_m._billing.charge.assert_called_once_with(consumer_api_key="ck_test", tool_name="stability", cost=0.002)


async def test_stability_insufficient_balance(stability_fn, mock_m):
    mock_m._billing.check_balance.side_effect = InsufficientBalanceError("no funds")

    with pytest.raises(InsufficientBalanceError):
        await stability_fn("a sunset", consumer_api_key="ck_test")

    mock_m._billing.charge.assert_not_called()


async def test_stability_gateway_error(stability_fn, mock_m):
    mock_m._billing.check_balance.side_effect = GatewayError("timeout")

    with pytest.raises(GatewayError):
        await stability_fn("a sunset", consumer_api_key="ck_test")

    mock_m._billing.charge.assert_not_called()


async def test_stability_api_failure_no_charge(stability_fn, mock_m):
    with patch("httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_cls.return_value)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value.post = AsyncMock(side_effect=Exception("Stability 503"))
        result = await stability_fn("a sunset", consumer_api_key="ck_test")

    assert result.startswith("Error:")
    mock_m._billing.charge.assert_not_called()
