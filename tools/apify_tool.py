import os
import json
import asyncio
from apify_client import ApifyClient
from metrify import UpstreamError
from auth.middleware import _current_consumer_key


def _handle_error(e: Exception) -> str:
    if "Unauthorized" in str(e) or "401" in str(e):
        return "Error: Invalid Apify token. Check APIFY_API_KEY."
    if "Not Found" in str(e) or "404" in str(e):
        return "Error: Apify actor not found. Verify the actor_id."
    if "timeout" in str(e).lower():
        return "Error: Apify actor run timed out. Try increasing the actor's timeout settings."
    return f"Error: {type(e).__name__}: {e}"


def register(server, m):
    # Inner: billing-wrapped. tool_name="apify" from func.__name__.
    @m.tool(price=0.005, unit="per_call")
    async def apify(consumer_api_key: str, actor_id: str, run_input: dict) -> str:
        api_token = os.environ["APIFY_API_KEY"]
        loop = asyncio.get_running_loop()
        client = ApifyClient(api_token)
        try:
            run = await loop.run_in_executor(
                None, lambda: client.actor(actor_id).call(run_input=run_input)
            )
            items = await loop.run_in_executor(
                None, lambda: list(client.dataset(run["defaultDatasetId"]).iterate_items())
            )
            return json.dumps(items)
        except Exception as e:
            raise UpstreamError(_handle_error(e)) from e

    _billed = apify

    # Outer: MCP-facing. consumer_api_key optional (JWT or param).
    @server.tool(
        name="apify",
        annotations={
            "title": "Apify Actor Run",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def apify_mcp(
        actor_id: str,
        run_input: dict,
        consumer_api_key: str = "",
    ) -> str:
        """Run an Apify actor and return its dataset results as JSON.

        Billed at $0.005 per call via Metrify. Runs the actor synchronously and
        waits for completion before returning all dataset items.

        Args:
            actor_id: Apify actor ID or username/actor-name (e.g. "apify/web-scraper").
            run_input: Dictionary of input parameters for the actor.
            consumer_api_key: Metrify consumer key (format: ck_...). Optional when
                using OAuth Bearer JWT — the key is read from the token instead.

        Returns:
            JSON string of the actor's dataset items, or an error message prefixed
            with "Error:".
        """
        resolved_key = _current_consumer_key.get() or consumer_api_key
        if not resolved_key:
            return "Error: autenticación requerida. Usá OAuth o pasá consumer_api_key."
        return await _billed(
            consumer_api_key=resolved_key,
            actor_id=actor_id,
            run_input=run_input,
        )

    return apify_mcp
