from decimal import Decimal
from typing import Optional, Tuple

import httpx

from src.config import settings
from src.wrappers.base import BaseMCPWrapper, UpstreamError

# $0.37/hour → $0.00617/minute
_COST_PER_MINUTE = Decimal("0.00617")
_BASE_URL = "https://api.assemblyai.com/v2"
_DEFAULT_DURATION_SECONDS = 60


class AssemblyAIWrapper(BaseMCPWrapper):
    tool_name = "assemblyai"

    async def estimate_cost(self, params: dict) -> Decimal:
        duration_seconds = params.get("duration_seconds", _DEFAULT_DURATION_SECONDS)
        duration_minutes = Decimal(str(duration_seconds)) / Decimal("60")
        return (duration_minutes * _COST_PER_MINUTE).quantize(Decimal("0.000001"))

    async def call(self, params: dict) -> Tuple[dict, Decimal]:
        audio_url = params.get("audio_url", "")
        language_code = params.get("language_code", "en")
        estimated_duration_seconds = params.get("duration_seconds", _DEFAULT_DURATION_SECONDS)

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                transcript = await self._submit_and_poll(
                    client, audio_url, language_code
                )
        except httpx.HTTPStatusError as exc:
            raise UpstreamError(str(exc), status_code=exc.response.status_code) from exc
        except httpx.RequestError as exc:
            raise UpstreamError(str(exc), status_code=0) from exc

        audio_duration = transcript.get("audio_duration")
        if audio_duration is not None:
            duration_seconds = float(audio_duration)
        else:
            duration_seconds = float(estimated_duration_seconds)

        duration_minutes = Decimal(str(duration_seconds)) / Decimal("60")
        actual_cost = (duration_minutes * _COST_PER_MINUTE).quantize(Decimal("0.000001"))

        return {
            "transcript_id": transcript.get("id", ""),
            "text": transcript.get("text", ""),
            "status": transcript.get("status", "completed"),
            "audio_duration_seconds": duration_seconds,
            "language_code": transcript.get("language_code", language_code),
            "usage": {"audio_duration_seconds": duration_seconds},
        }, actual_cost

    async def _submit_and_poll(
        self, client: httpx.AsyncClient, audio_url: str, language_code: str
    ) -> dict:
        headers = {"authorization": settings.assemblyai_api_key}

        submit_resp = await client.post(
            f"{_BASE_URL}/transcript",
            headers=headers,
            json={"audio_url": audio_url, "language_code": language_code},
        )
        submit_resp.raise_for_status()
        transcript_id = submit_resp.json()["id"]

        import asyncio
        for _ in range(60):
            poll_resp = await client.get(
                f"{_BASE_URL}/transcript/{transcript_id}",
                headers=headers,
            )
            poll_resp.raise_for_status()
            data = poll_resp.json()
            if data["status"] == "completed":
                return data
            if data["status"] == "error":
                raise UpstreamError(
                    data.get("error", "AssemblyAI transcription failed"),
                    status_code=0,
                )
            await asyncio.sleep(3)

        raise UpstreamError("AssemblyAI transcription timed out", status_code=0)

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{_BASE_URL}/transcript",
                    headers={"authorization": settings.assemblyai_api_key},
                    params={"limit": 1},
                )
                return resp.status_code == 200
        except Exception:
            return False
