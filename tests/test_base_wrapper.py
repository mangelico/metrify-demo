from decimal import Decimal

import pytest

from src.wrappers.base import BaseMCPWrapper, UpstreamError


class ConcreteWrapper(BaseMCPWrapper):
    tool_name = "test_tool"

    async def estimate_cost(self, params: dict) -> Decimal:
        return Decimal("0.001")

    async def call(self, params: dict):
        return ({"output": "ok"}, Decimal("0.001"))

    async def health_check(self) -> bool:
        return True


def test_cannot_instantiate_abstract():
    with pytest.raises(TypeError):
        BaseMCPWrapper()  # type: ignore


def test_concrete_subclass_instantiates():
    w = ConcreteWrapper()
    assert w.tool_name == "test_tool"


@pytest.mark.asyncio
async def test_estimate_cost():
    w = ConcreteWrapper()
    cost = await w.estimate_cost({})
    assert isinstance(cost, Decimal)


@pytest.mark.asyncio
async def test_call_returns_tuple():
    w = ConcreteWrapper()
    result, cost = await w.call({})
    assert isinstance(result, dict)
    assert isinstance(cost, Decimal)


@pytest.mark.asyncio
async def test_health_check():
    w = ConcreteWrapper()
    assert await w.health_check() is True


def test_upstream_error_carries_status():
    err = UpstreamError("boom", status_code=500)
    assert err.status_code == 500
    assert str(err) == "boom"
