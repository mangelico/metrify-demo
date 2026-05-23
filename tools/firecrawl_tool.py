import os
import asyncio
from firecrawl import FirecrawlApp
from metrify import UpstreamError


def _handle_error(e: Exception) -> str:
    if "401" in str(e) or "Unauthorized" in str(e):
        return "Error: Invalid Firecrawl API key. Check FIRECRAWL_API_KEY."
    if "403" in str(e) or "blocked" in str(e).lower():
        return "Error: Firecrawl was blocked by the target website. Try a different URL."
    if "timeout" in str(e).lower():
        return "Error: Firecrawl request timed out. The page may be too heavy to scrape."
    return f"Error: {type(e).__name__}: {e}"


def register(server, m):
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
    @m.tool(price=0.001, unit="per_page")
    async def firecrawl(consumer_api_key: str, url: str) -> str:
        """Scrape a web page and return its content as clean Markdown.

        Billed at $0.001 per page via Metrify. Uses Firecrawl to extract readable
        content, stripping navigation, ads, and boilerplate.

        Args:
            consumer_api_key: Metrify consumer key (format: ck_...).
            url: Full URL of the page to scrape (e.g. "https://example.com/article").

        Returns:
            Markdown-formatted page content, or an error message prefixed with "Error:".
        """
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

    return firecrawl
