import json
import pytest
from unittest.mock import MagicMock, patch
from metrify import InsufficientBalanceError, GatewayError


@pytest.fixture
def apify_fn(mock_server, mock_m):
    from tools.apify_tool import register
    return register(mock_server, mock_m)


async def test_apify_happy_path(apify_fn, mock_m):
    items = [{"title": "Result 1"}, {"title": "Result 2"}]

    with patch("tools.apify_tool.ApifyClient") as mock_cls:
        mock_client = mock_cls.return_value
        mock_client.actor.return_value.call.return_value = {"defaultDatasetId": "ds_abc"}
        mock_client.dataset.return_value.iterate_items.return_value = iter(items)
        result = await apify_fn("ck_test", "apify/web-scraper", {"startUrls": []})

    assert json.loads(result) == items
    mock_m._billing.check_balance.assert_called_once_with(consumer_api_key="ck_test", required=0.005)
    mock_m._billing.charge.assert_called_once_with(consumer_api_key="ck_test", tool_name="apify", cost=0.005)


async def test_apify_insufficient_balance(apify_fn, mock_m):
    mock_m._billing.check_balance.side_effect = InsufficientBalanceError("no funds")

    with pytest.raises(InsufficientBalanceError):
        await apify_fn("ck_test", "apify/web-scraper", {})

    mock_m._billing.charge.assert_not_called()


async def test_apify_gateway_error(apify_fn, mock_m):
    mock_m._billing.check_balance.side_effect = GatewayError("timeout")

    with pytest.raises(GatewayError):
        await apify_fn("ck_test", "apify/web-scraper", {})

    mock_m._billing.charge.assert_not_called()


async def test_apify_actor_failure_no_charge(apify_fn, mock_m):
    with patch("tools.apify_tool.ApifyClient") as mock_cls:
        mock_cls.return_value.actor.return_value.call.side_effect = Exception("Actor failed")
        result = await apify_fn("ck_test", "apify/web-scraper", {})

    assert result.startswith("Error:")
    mock_m._billing.charge.assert_not_called()
