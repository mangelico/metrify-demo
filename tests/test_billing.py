"""
Verifies that @m.tool() correctly invokes the billing SDK:
- consumer_api_key propagated to check_balance and charge
- correct price for each tool
- charge not called when upstream fails
- charge not called when balance insufficient
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from metrify import Metrify
from metrify.exceptions import InsufficientBalanceError, GatewayError, UpstreamError


@pytest.fixture
def m():
    instance = Metrify()
    instance._billing.check_balance = MagicMock()
    instance._billing.charge = MagicMock()
    return instance


def passthrough_server():
    s = MagicMock()
    s.tool.return_value = lambda f: f
    return s


async def test_billing_check_called_before_function(m):
    execution_order = []
    m._billing.check_balance.side_effect = lambda *a, **kw: execution_order.append("check_balance")

    @m.tool(price=0.01, unit="per_call")
    async def fn(consumer_api_key: str) -> str:
        execution_order.append("fn")
        return "ok"

    await fn("ck_test")
    assert execution_order == ["check_balance", "fn"]


async def test_billing_charge_called_after_function(m):
    execution_order = []

    @m.tool(price=0.01, unit="per_call")
    async def fn(consumer_api_key: str) -> str:
        execution_order.append("fn")
        return "ok"

    m._billing.charge.side_effect = lambda *a, **kw: execution_order.append("charge")
    await fn("ck_test")
    assert execution_order == ["fn", "charge"]


async def test_billing_consumer_key_propagated(m):
    @m.tool(price=0.005, unit="per_call")
    async def fn(consumer_api_key: str) -> str:
        return "ok"

    await fn("ck_consumer_xyz")
    m._billing.check_balance.assert_called_once_with(consumer_api_key="ck_consumer_xyz", required=0.005)
    m._billing.charge.assert_called_once_with(consumer_api_key="ck_consumer_xyz", tool_name="fn", cost=0.005)


async def test_billing_correct_price_anthropic(m):
    s = passthrough_server()
    from tools.anthropic_tool import register
    from unittest.mock import patch, AsyncMock as AM
    from auth.middleware import _current_consumer_key

    fn = register(s, m)
    mock_resp = MagicMock()
    mock_resp.content = [MagicMock(text="hi")]
    tok = _current_consumer_key.set("ck_test")
    try:
        with patch("anthropic.AsyncAnthropic") as cls:
            cls.return_value.messages.create = AM(return_value=mock_resp)
            await fn("hi")
    finally:
        _current_consumer_key.reset(tok)

    m._billing.check_balance.assert_called_once()
    assert m._billing.check_balance.call_args.kwargs["required"] == 0.000065


async def test_billing_correct_price_stability(m):
    s = passthrough_server()
    from tools.stability_tool import register
    from unittest.mock import patch, AsyncMock as AM
    from auth.middleware import _current_consumer_key

    fn = register(s, m)
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"artifacts": [{"base64": "x"}]}
    mock_resp.raise_for_status = MagicMock()
    tok = _current_consumer_key.set("ck_test")
    try:
        with patch("httpx.AsyncClient") as cls:
            cls.return_value.__aenter__ = AM(return_value=cls.return_value)
            cls.return_value.__aexit__ = AM(return_value=False)
            cls.return_value.post = AM(return_value=mock_resp)
            await fn("a dog")
    finally:
        _current_consumer_key.reset(tok)

    m._billing.check_balance.assert_called_once()
    assert m._billing.check_balance.call_args.kwargs["required"] == 0.002


async def test_billing_no_charge_on_insufficient_balance(m):
    m._billing.check_balance.side_effect = InsufficientBalanceError("no funds")

    @m.tool(price=0.01, unit="per_call")
    async def fn(consumer_api_key: str) -> str:
        return "ok"

    with pytest.raises(InsufficientBalanceError):
        await fn("ck_test")
    m._billing.charge.assert_not_called()


async def test_billing_no_charge_on_upstream_failure(m):
    @m.tool(price=0.01, unit="per_call")
    async def fn(consumer_api_key: str) -> str:
        raise UpstreamError("Error: upstream dead")

    result = await fn("ck_test")
    assert "Error:" in result
    m._billing.charge.assert_not_called()
