import os
import openai as openai_client
import httpx
from metrify import UpstreamError
from auth.middleware import _current_consumer_key


def _handle_error(e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code == 429:
            return "Error: OpenAI rate limit exceeded. Please retry in a moment."
        if e.response.status_code == 401:
            return "Error: Invalid OpenAI API key. Check OPENAI_API_KEY."
        return f"Error: OpenAI API returned status {e.response.status_code}."
    if isinstance(e, httpx.TimeoutException):
        return "Error: OpenAI request timed out. Please retry."
    return f"Error: {type(e).__name__}: {e}"


def register(server, m):
    # Inner: billing-wrapped. tool_name="openai" from func.__name__.
    @m.tool(price=0.000010, unit="per_token", description="Text generation via GPT-4o-mini (OpenAI). Per token.")
    async def openai(consumer_api_key: str, prompt: str, max_tokens: int = 1024) -> str:
        if len(prompt) > 2000:
            raise UpstreamError(
                f"Error: Prompt too long ({len(prompt)} chars). Demo tier limit: 2000 chars (~500 tokens)."
            )
        max_tokens = min(max_tokens, 512)
        try:
            client = openai_client.AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            raise UpstreamError(_handle_error(e)) from e

    _billed = openai

    # Outer: MCP-facing. consumer_api_key optional (JWT or param).
    @server.tool(
        name="openai",
        annotations={
            "title": "OpenAI GPT Text Generation",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def openai_mcp(prompt: str, max_tokens: int = 1024) -> str:
        """Generate text using OpenAI gpt-4o-mini.

        Billed at $0.000010 per token via Metrify. The consumer is charged only
        if the upstream call succeeds. Requires OAuth Bearer JWT authentication.
        Demo limits: 2000 char prompt, 512 token response.

        Args:
            prompt: Text prompt to send to the model.
            max_tokens: Maximum tokens in the response (default 1024, capped at 512).

        Returns:
            Generated text string, or an error message prefixed with "Error:" on failure.
        """
        resolved_key = _current_consumer_key.get()
        if not resolved_key:
            return "Error: sin autenticación"
        return await _billed(
            consumer_api_key=resolved_key,
            prompt=prompt,
            max_tokens=max_tokens,
        )

    return openai_mcp
