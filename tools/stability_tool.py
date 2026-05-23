import os
import httpx
from metrify import UpstreamError


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
    @m.tool(price=0.002, unit="per_image")
    async def stability(consumer_api_key: str, prompt: str, model: str = "sdxl") -> str:
        """Generate an image using Stability AI SDXL and return it as base64.

        Billed at $0.002 per image via Metrify. V1 limitation: price is fixed for
        sdxl regardless of the `model` parameter — sd3 ($0.035) is not yet supported.

        Args:
            consumer_api_key: Metrify consumer key (format: ck_...).
            prompt: Text description of the image to generate.
            model: Model hint (default "sdxl"). Note: only sdxl pricing in V1.

        Returns:
            Base64-encoded PNG image string, or an error message prefixed with "Error:".
        """
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

    return stability
