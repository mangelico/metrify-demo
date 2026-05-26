import os
import anthropic as anthropic_client
import httpx
from metrify import UpstreamError


def _handle_error(e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code == 429:
            return "Error: Anthropic rate limit exceeded. Please retry in a moment."
        if e.response.status_code == 401:
            return "Error: Invalid Anthropic API key. Check ANTHROPIC_API_KEY."
        return f"Error: Anthropic API returned status {e.response.status_code}."
    if isinstance(e, httpx.TimeoutException):
        return "Error: Anthropic request timed out. Please retry."
    return f"Error: {type(e).__name__}: {e}"


def register(server, m):
    @server.tool(
        name="anthropic",
        annotations={
            "title": "Anthropic Claude Text Generation",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    @m.tool(price=0.000065, unit="per_token")
    async def anthropic(consumer_api_key: str, prompt: str, max_tokens: int = 1024) -> str:
        """Generate text using Anthropic claude-haiku-4-5.

        Billed at $0.000065 per token via Metrify. The consumer is charged only
        if the upstream call succeeds.
        Demo limits: 2000 char prompt, 512 token response.

        Args:
            consumer_api_key: Metrify consumer key (format: ck_...).
            prompt: Text prompt to send to the model.
            max_tokens: Maximum tokens in the response (default 1024, capped at 512).

        Returns:
            Generated text string, or an error message prefixed with "Error:" on failure.
        """
        if len(prompt) > 2000:
            raise UpstreamError(
                f"Error: Prompt too long ({len(prompt)} chars). Demo tier limit: 2000 chars (~500 tokens)."
            )
        max_tokens = min(max_tokens, 512)
        try:
            client = anthropic_client.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
            response = await client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except Exception as e:
            raise UpstreamError(_handle_error(e)) from e

    return anthropic
