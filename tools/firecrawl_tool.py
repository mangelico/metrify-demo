import os
import asyncio
from firecrawl import FirecrawlApp
from metrify import UpstreamError
from auth.middleware import _current_consumer_key


def _handle_error(e: Exception) -> str:
    if "401" in str(e) or "Unauthorized" in str(e):
        return "Error: Invalid Firecrawl API key. Check FIRECRAWL_API_KEY."
    if "403" in str(e) or "blocked" in str(e).lower():
        return "Error: Firecrawl was blocked by the target website. Try a different URL."
    if "timeout" in str(e).lower():
        return "Error: Firecrawl request timed out. The page may be too heavy to scrape."
    return f"Error: {type(e).__name__}: {e}"


def register(server, m):
    # Inner: billing-wrapped. tool_name="firecrawl" from func.__name__.
    @m.tool(price=0.001, unit="per_page")
    async def firecrawl(consumer_api_key: str, url: str) -> str:
        api_key = os.environ["FIRECRAWL_API_KEY"]
        loop = asyncio.get_running_loop()
        app = FirecrawlApp(api_key=api_key)
        try:
            result = await loop.run_in_executor(
                None, lambda: app.scrape_url(url, {"formats": ["markdown"]})
            )
            return result.get("markdown", "")
        except Exception as e:
            raise UpstreamError(_handle_error(e)) from e

    _billed = firecrawl

    # Outer: MCP-facing. consumer_api_key optional (JWT or param).
    @server.tool(
        name="firecrawl",
        annotations={
            "title": "Firecrawl Web Page Scraper",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def firecrawl_mcp(url: str) -> str:
        """Scrape a web page and return its content as clean Markdown.

        Billed at $0.001 per page via Metrify. Requires OAuth Bearer JWT
        authentication. Uses Firecrawl to extract readable content.

        Args:
            url: Full URL of the page to scrape (e.g. "https://example.com/article").

        Returns:
            Markdown-formatted page content, or an error message prefixed with "Error:".
        """
        resolved_key = _current_consumer_key.get()
        if not resolved_key:
            return "Error: sin autenticación"
        return await _billed(
            consumer_api_key=resolved_key,
            url=url,
        )

    return firecrawl_mcp
