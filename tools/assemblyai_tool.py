import os
import asyncio
import httpx
from metrify import UpstreamError
from auth.middleware import _current_consumer_key

_BASE = "https://api.assemblyai.com/v2"


def _handle_error(e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code == 401:
            return "Error: Invalid AssemblyAI API key. Check ASSEMBLYAI_API_KEY."
        if e.response.status_code == 400:
            return "Error: AssemblyAI rejected the request. Verify the audio URL is publicly accessible."
        return f"Error: AssemblyAI returned status {e.response.status_code}."
    if isinstance(e, httpx.TimeoutException):
        return "Error: AssemblyAI request timed out. Please retry."
    return f"Error: {type(e).__name__}: {e}"


def register(server, m):
    # Inner: billing-wrapped. tool_name="assemblyai" from func.__name__.
    @m.tool(price=0.00617, unit="per_minute")
    async def assemblyai(consumer_api_key: str, audio_url: str) -> str:
        api_key = os.environ["ASSEMBLYAI_API_KEY"]
        headers = {"authorization": api_key, "content-type": "application/json"}

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{_BASE}/transcript",
                    json={"audio_url": audio_url},
                    headers=headers,
                    timeout=30.0,
                )
                resp.raise_for_status()
                transcript_id = resp.json()["id"]

                while True:
                    resp = await client.get(
                        f"{_BASE}/transcript/{transcript_id}",
                        headers=headers,
                        timeout=30.0,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    if data["status"] == "completed":
                        audio_duration = data.get("audio_duration")
                        if audio_duration is not None and audio_duration > 300:
                            raise UpstreamError(
                                "Error: Audio too long. Demo tier limit: 5 minutes."
                            )
                        return data["text"] or ""
                    if data["status"] == "error":
                        raise UpstreamError(
                            f"Error: Transcription failed: {data.get('error', 'unknown error')}"
                        )
                    await asyncio.sleep(2)
        except UpstreamError:
            raise
        except Exception as e:
            raise UpstreamError(_handle_error(e)) from e

    _billed = assemblyai

    # Outer: MCP-facing. consumer_api_key optional (JWT or param).
    @server.tool(
        name="assemblyai",
        annotations={
            "title": "AssemblyAI Audio Transcription",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def assemblyai_mcp(
        audio_url: str,
        consumer_api_key: str = "",
    ) -> str:
        """Transcribe audio to text using AssemblyAI.

        Billed at $0.00617 per minute of audio via Metrify. The audio URL must be
        publicly accessible. Uses AssemblyAI REST API v2 directly.
        Demo limits: 5 min audio max.

        Args:
            audio_url: Publicly accessible URL of the audio file to transcribe.
            consumer_api_key: Metrify consumer key (format: ck_...). Optional when
                using OAuth Bearer JWT — the key is read from the token instead.

        Returns:
            Transcribed text string, or an error message prefixed with "Error:".
        """
        resolved_key = _current_consumer_key.get() or consumer_api_key
        if not resolved_key:
            return "Error: autenticación requerida. Usá OAuth o pasá consumer_api_key."
        return await _billed(
            consumer_api_key=resolved_key,
            audio_url=audio_url,
        )

    return assemblyai_mcp
