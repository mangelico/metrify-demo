import asyncio
from decimal import Decimal
from typing import Tuple

import httpx

from src.config import settings
from src.wrappers.base import BaseMCPWrapper, UpstreamError

_COST_PER_RUN = Decimal("0.005")
_BASE_URL = "https://api.apify.com/v2"
_POLL_TIMEOUT_SECONDS = 60
_POLL_INTERVAL_SECONDS = 3


class ApifyWrapper(BaseMCPWrapper):
    tool_name = "apify"

    async def estimate_cost(self, params: dict) -> Decimal:
        return _COST_PER_RUN

    async def call(self, params: dict) -> Tuple[dict, Decimal]:
        actor_id = params.get("actor_id", "apify/web-scraper")
        run_input = params.get("input", {})

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                run_id = await self._start_run(client, actor_id, run_input)
                final_status, output = await self._poll_run(client, run_id)
        except UpstreamError:
            raise
        except httpx.HTTPStatusError as exc:
            raise UpstreamError(str(exc), status_code=exc.response.status_code) from exc
        except httpx.RequestError as exc:
            raise UpstreamError(str(exc), status_code=0) from exc

        if final_status == "pending":
            return {
                "status": "pending",
                "run_id": run_id,
                "message": "Run did not complete within timeout. Poll again using run_id.",
            }, Decimal("0")

        if final_status == "FAILED":
            raise UpstreamError(f"Apify run {run_id} failed", status_code=0)

        return {
            "status": "SUCCEEDED",
            "run_id": run_id,
            "output": output,
            "usage": {"runs": 1},
        }, _COST_PER_RUN

    async def _start_run(
        self, client: httpx.AsyncClient, actor_id: str, run_input: dict
    ) -> str:
        resp = await client.post(
            f"{_BASE_URL}/acts/{actor_id}/runs",
            headers={"Authorization": f"Bearer {settings.apify_api_token}"},
            json=run_input,
        )
        resp.raise_for_status()
        return resp.json()["data"]["id"]

    async def _poll_run(
        self, client: httpx.AsyncClient, run_id: str
    ) -> Tuple[str, dict]:
        elapsed = 0
        while elapsed < _POLL_TIMEOUT_SECONDS:
            resp = await client.get(
                f"{_BASE_URL}/actor-runs/{run_id}",
                headers={"Authorization": f"Bearer {settings.apify_api_token}"},
            )
            resp.raise_for_status()
            data = resp.json()["data"]
            status = data["status"]

            if status == "SUCCEEDED":
                output = await self._fetch_output(client, run_id)
                return "SUCCEEDED", output
            if status in ("FAILED", "ABORTED", "TIMED-OUT"):
                return "FAILED", {}

            await asyncio.sleep(_POLL_INTERVAL_SECONDS)
            elapsed += _POLL_INTERVAL_SECONDS

        return "pending", {}

    async def _fetch_output(self, client: httpx.AsyncClient, run_id: str) -> dict:
        resp = await client.get(
            f"{_BASE_URL}/actor-runs/{run_id}/dataset/items",
            headers={"Authorization": f"Bearer {settings.apify_api_token}"},
            params={"format": "json", "limit": 100},
        )
        resp.raise_for_status()
        return {"items": resp.json()}

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{_BASE_URL}/acts",
                    headers={"Authorization": f"Bearer {settings.apify_api_token}"},
                    params={"limit": 1},
                )
                return resp.status_code == 200
        except Exception:
            return False
