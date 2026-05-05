from decimal import Decimal
from typing import Tuple

import httpx

from src.config import settings
from src.wrappers.base import BaseMCPWrapper, UpstreamError

_PRICING = {
    "sdxl": Decimal("0.002"),
    "sd3": Decimal("0.035"),
}
_DEFAULT_MODEL = "sdxl"
_SDXL_ENGINE = "stable-diffusion-xl-1024-v1-0"
_STABILITY_BASE = "https://api.stability.ai"


class StabilityWrapper(BaseMCPWrapper):
    tool_name = "stability"

    async def estimate_cost(self, params: dict) -> Decimal:
        model = params.get("model", _DEFAULT_MODEL)
        return _PRICING.get(model, _PRICING[_DEFAULT_MODEL])

    async def call(self, params: dict) -> Tuple[dict, Decimal]:
        model = params.get("model", _DEFAULT_MODEL)
        prompt = params.get("prompt", "")
        width = params.get("width", 1024)
        height = params.get("height", 1024)
        price = _PRICING.get(model, _PRICING[_DEFAULT_MODEL])

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                if model == "sd3":
                    result = await self._call_sd3(client, prompt)
                else:
                    result = await self._call_sdxl(client, prompt, width, height)
        except httpx.HTTPStatusError as exc:
            raise UpstreamError(str(exc), status_code=exc.response.status_code) from exc
        except httpx.RequestError as exc:
            raise UpstreamError(str(exc), status_code=0) from exc

        return result, price

    async def _call_sdxl(
        self, client: httpx.AsyncClient, prompt: str, width: int, height: int
    ) -> dict:
        resp = await client.post(
            f"{_STABILITY_BASE}/v1/generation/{_SDXL_ENGINE}/text-to-image",
            headers={
                "Authorization": f"Bearer {settings.stability_api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json={
                "text_prompts": [{"text": prompt, "weight": 1.0}],
                "width": width,
                "height": height,
                "samples": 1,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        artifact = data["artifacts"][0]
        return {
            "model": "sdxl",
            "image_b64": artifact["base64"],
            "finish_reason": artifact.get("finishReason", "SUCCESS"),
        }

    async def _call_sd3(self, client: httpx.AsyncClient, prompt: str) -> dict:
        resp = await client.post(
            f"{_STABILITY_BASE}/v2beta/stable-image/generate/sd3",
            headers={
                "Authorization": f"Bearer {settings.stability_api_key}",
                "Accept": "application/json",
            },
            data={"prompt": prompt, "output_format": "png"},
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "model": "sd3",
            "image_b64": data.get("image", ""),
            "finish_reason": data.get("finish_reason", "SUCCESS"),
        }

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{_STABILITY_BASE}/v1/engines/list",
                    headers={"Authorization": f"Bearer {settings.stability_api_key}"},
                )
                return resp.status_code == 200
        except Exception:
            return False
