import os
import httpx
from metrify import UpstreamError
from auth.middleware import _current_consumer_key


def _handle_error(e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code == 402:
            return "Error: Stability AI credits exhausted. Check your account balance."
        if e.response.status_code == 401:
            return "Error: Invalid Stability AI API key. Check STABILITY_API_KEY."
        if e.response.status_code == 429:
            return "Error: Stability AI rate limit exceeded. Please retry in a moment."
        return f"Error: Stability AI returned status {e.response.status_code}."
    if isinstance(e, httpx.TimeoutException):
        return "Error: Stability AI request timed out (image generation can take up to 60s). Please retry."
    return f"Error: {type(e).__name__}: {e}"


def register(server, m):
    # Inner: billing-wrapped. tool_name="stability" from func.__name__.
    @m.tool(price=0.002, unit="per_image", description="Image generation via Stability AI SDXL. Per image.")
    async def stability(consumer_api_key: str, prompt: str, model: str = "sdxl") -> str:
        api_key = os.environ["STABILITY_API_KEY"]
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                    },
                    json={
                        "text_prompts": [{"text": prompt, "weight": 1}],
                        "cfg_scale": 7,
                        "height": 1024,
                        "width": 1024,
                        "steps": 30,
                        "samples": 1,
                    },
                    timeout=60.0,
                )
                response.raise_for_status()
                data = response.json()
                return data["artifacts"][0]["base64"]
        except Exception as e:
            raise UpstreamError(_handle_error(e)) from e

    _billed = stability

    # Outer: MCP-facing. consumer_api_key optional (JWT or param).
    @server.tool(
        name="stability",
        annotations={
            "title": "Stability AI Image Generation",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def stability_mcp(prompt: str, model: str = "sdxl") -> str:
        """Generate an image using Stability AI SDXL and return it as base64.

        Billed at $0.002 per image via Metrify. Requires OAuth Bearer JWT authentication.
        V1 limitation: price is fixed for sdxl — sd3 ($0.035) is not yet supported.

        Args:
            prompt: Text description of the image to generate.
            model: Model hint (default "sdxl"). Note: only sdxl pricing in V1.

        Returns:
            Base64-encoded PNG image string, or an error message prefixed with "Error:".
        """
        resolved_key = _current_consumer_key.get()
        if not resolved_key:
            return "Error: sin autenticación"
        return await _billed(
            consumer_api_key=resolved_key,
            prompt=prompt,
            model=model,
        )

    return stability_mcp
