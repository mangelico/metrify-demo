import os
import openai as openai_client
import httpx
from metrify import UpstreamError


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
    @m.tool(price=0.000010, unit="per_token")
    async def openai(consumer_api_key: str, prompt: str, max_tokens: int = 1024) -> str:
        """Generate text using OpenAI gpt-4o-mini.

        Billed at $0.000010 per token via Metrify. The consumer is charged only
        if the upstream call succeeds.

        Args:
            consumer_api_key: Metrify consumer key (format: ck_...).
            prompt: Text prompt to send to the model.
            max_tokens: Maximum tokens in the response (default 1024).

        Returns:
            Generated text string, or an error message prefixed with "Error:" on failure.
        """
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

    return openai
