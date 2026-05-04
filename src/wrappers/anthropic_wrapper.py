from decimal import Decimal
from typing import List, Tuple

import anthropic

from src.config import settings
from src.wrappers.base import BaseMCPWrapper, UpstreamError

# Pricing in USDT (= USD) per token — claude-haiku-4-5
_INPUT_PRICE_PER_TOKEN = Decimal("0.0000008")   # $0.80 / 1M
_OUTPUT_PRICE_PER_TOKEN = Decimal("0.000004")   # $4.00 / 1M

_DEFAULT_MODEL = "claude-haiku-4-5-20251001"


def _token_cost(input_tokens: int, output_tokens: int) -> Decimal:
    return (
        Decimal(input_tokens) * _INPUT_PRICE_PER_TOKEN
        + Decimal(output_tokens) * _OUTPUT_PRICE_PER_TOKEN
    )


class AnthropicWrapper(BaseMCPWrapper):
    tool_name = "anthropic"

    def __init__(self) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def estimate_cost(self, params: dict) -> Decimal:
        # Estimate: count chars/4 as rough token proxy for input,
        # use max_tokens for output upper bound.
        messages: List[dict] = params.get("messages", [])
        input_chars = sum(len(str(m.get("content", ""))) for m in messages)
        estimated_input = max(input_chars // 4, 1)
        max_tokens: int = params.get("max_tokens", 1024)
        return _token_cost(estimated_input, max_tokens)

    async def call(self, params: dict) -> Tuple[dict, Decimal]:
        model = params.get("model", _DEFAULT_MODEL)
        messages = params.get("messages", [])
        max_tokens = params.get("max_tokens", 1024)
        system = params.get("system")

        try:
            kwargs = dict(model=model, messages=messages, max_tokens=max_tokens)
            if system:
                kwargs["system"] = system

            response = await self._client.messages.create(**kwargs)
        except anthropic.APIStatusError as exc:
            raise UpstreamError(str(exc), status_code=exc.status_code) from exc
        except anthropic.APIConnectionError as exc:
            raise UpstreamError(str(exc), status_code=0) from exc

        usage = response.usage
        actual_cost = _token_cost(usage.input_tokens, usage.output_tokens)

        result = {
            "id": response.id,
            "model": response.model,
            "content": [{"type": b.type, "text": b.text} for b in response.content],
            "usage": {
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
            },
            "stop_reason": response.stop_reason,
        }
        return result, actual_cost

    async def health_check(self) -> bool:
        try:
            await self._client.messages.create(
                model=_DEFAULT_MODEL,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
            )
            return True
        except Exception:
            return False
