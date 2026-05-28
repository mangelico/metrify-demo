import pytest
from unittest.mock import MagicMock, patch
from metrify import InsufficientBalanceError, GatewayError


@pytest.fixture
def firecrawl_fn(mock_server, mock_m):
    from tools.firecrawl_tool import register
    return register(mock_server, mock_m)


async def test_firecrawl_happy_path(firecrawl_fn, mock_m):
    with patch("tools.firecrawl_tool.FirecrawlApp") as mock_cls:
        mock_cls.return_value.scrape_url.return_value = {
            "markdown": "# Page Title\n\nContent here."
        }
        result = await firecrawl_fn("https://example.com", consumer_api_key="ck_test")

    assert result == "# Page Title\n\nContent here."
    mock_m._billing.check_balance.assert_called_once_with(consumer_api_key="ck_test", required=0.001)
    mock_m._billing.charge.assert_called_once_with(consumer_api_key="ck_test", tool_name="firecrawl", cost=0.001)


async def test_firecrawl_insufficient_balance(firecrawl_fn, mock_m):
    mock_m._billing.check_balance.side_effect = InsufficientBalanceError("no funds")

    with pytest.raises(InsufficientBalanceError):
        await firecrawl_fn("https://example.com", consumer_api_key="ck_test")

    mock_m._billing.charge.assert_not_called()


async def test_firecrawl_gateway_error(firecrawl_fn, mock_m):
    mock_m._billing.check_balance.side_effect = GatewayError("timeout")

    with pytest.raises(GatewayError):
        await firecrawl_fn("https://example.com", consumer_api_key="ck_test")

    mock_m._billing.charge.assert_not_called()


async def test_firecrawl_scrape_failure_no_charge(firecrawl_fn, mock_m):
    with patch("tools.firecrawl_tool.FirecrawlApp") as mock_cls:
        mock_cls.return_value.scrape_url.side_effect = Exception("Firecrawl 403 blocked")
        result = await firecrawl_fn("https://example.com", consumer_api_key="ck_test")

    assert result.startswith("Error:")
    mock_m._billing.charge.assert_not_called()
