from decimal import Decimal
from typing import Tuple

import httpx

from src.config import settings
from src.wrappers.base import BaseMCPWrapper, UpstreamError

_COST_PER_PAGE = Decimal("0.001")
_BASE_URL = "https://api.firecrawl.dev/v1"


class FirecrawlWrapper(BaseMCPWrapper):
    tool_name = "firecrawl"

    async def estimate_cost(self, params: dict) -> Decimal:
        return _COST_PER_PAGE

    async def call(self, params: dict) -> Tuple[dict, Decimal]:
        url = params.get("url", "")
        formats = params.get("formats", ["markdown"])

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                result = await self._scrape(client, url, formats)
        except httpx.HTTPStatusError as exc:
            raise UpstreamError(str(exc), status_code=exc.response.status_code) from exc
        except httpx.RequestError as exc:
            raise UpstreamError(str(exc), status_code=0) from exc

        return result, _COST_PER_PAGE

    async def _scrape(
        self, client: httpx.AsyncClient, url: str, formats: list
    ) -> dict:
        resp = await client.post(
            f"{_BASE_URL}/scrape",
            headers={
                "Authorization": f"Bearer {settings.firecrawl_api_key}",
                "Content-Type": "application/json",
            },
            json={"url": url, "formats": formats},
        )
        resp.raise_for_status()
        data = resp.json()

        if not data.get("success", False):
            raise UpstreamError(
                data.get("error", "Firecrawl scrape failed"), status_code=0
            )

        scraped = data.get("data", {})
        return {
            "url": url,
            "markdown": scraped.get("markdown", ""),
            "metadata": scraped.get("metadata", {}),
            "usage": {"pages": 1},
        }

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{_BASE_URL}/team/credit-usage",
                    headers={"Authorization": f"Bearer {settings.firecrawl_api_key}"},
                )
                return resp.status_code == 200
        except Exception:
            return False
