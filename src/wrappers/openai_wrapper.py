from decimal import Decimal
from typing import Tuple

import openai

from src.config import settings
from src.wrappers.base import BaseMCPWrapper, UpstreamError

# gpt-4o-mini pricing in USDT (= USD) per token
_INPUT_PRICE_PER_TOKEN = Decimal("0.00000015")   # $0.15 / 1M
_OUTPUT_PRICE_PER_TOKEN = Decimal("0.0000006")    # $0.60 / 1M

_DEFAULT_MODEL = "gpt-4o-mini"


def _token_cost(input_tokens: int, output_tokens: int) -> Decimal:
    return (
        Decimal(input_tokens) * _INPUT_PRICE_PER_TOKEN
        + Decimal(output_tokens) * _OUTPUT_PRICE_PER_TOKEN
    )


class OpenAIWrapper(BaseMCPWrapper):
    tool_name = "openai"

    def __init__(self) -> None:
        self._client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

    async def estimate_cost(self, params: dict) -> Decimal:
        messages = params.get("messages", [])
        input_chars = sum(len(str(m.get("content", ""))) for m in messages)
        estimated_input = max(input_chars // 4, 1)
        max_tokens: int = params.get("max_tokens", 1024)
        return _token_cost(estimated_input, max_tokens)

    async def call(self, params: dict) -> Tuple[dict, Decimal]:
        model = params.get("model", _DEFAULT_MODEL)
        messages = params.get("messages", [])
        max_tokens = params.get("max_tokens", 1024)

        try:
            response = await self._client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
            )
        except openai.APIStatusError as exc:
            raise UpstreamError(str(exc), status_code=exc.status_code) from exc
        except openai.APIConnectionError as exc:
            raise UpstreamError(str(exc), status_code=0) from exc

        usage = response.usage
        actual_cost = _token_cost(usage.prompt_tokens, usage.completion_tokens)

        result = {
            "id": response.id,
            "model": response.model,
            "content": [
                {"type": "text", "text": choice.message.content or ""}
                for choice in response.choices
            ],
            "usage": {
                "input_tokens": usage.prompt_tokens,
                "output_tokens": usage.completion_tokens,
            },
            "finish_reason": response.choices[0].finish_reason if response.choices else None,
        }
        return result, actual_cost

    async def health_check(self) -> bool:
        try:
            await self._client.chat.completions.create(
                model=_DEFAULT_MODEL,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
            )
            return True
        except Exception:
            return False
