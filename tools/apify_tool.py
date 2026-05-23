import os
import json
import asyncio
from apify_client import ApifyClient
from metrify import UpstreamError


def _handle_error(e: Exception) -> str:
    if "Unauthorized" in str(e) or "401" in str(e):
        return "Error: Invalid Apify token. Check APIFY_API_KEY."
    if "Not Found" in str(e) or "404" in str(e):
        return "Error: Apify actor not found. Verify the actor_id."
    if "timeout" in str(e).lower():
        return "Error: Apify actor run timed out. Try increasing the actor's timeout settings."
    return f"Error: {type(e).__name__}: {e}"


def register(server, m):
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
    @m.tool(price=0.005, unit="per_call")
    async def apify(consumer_api_key: str, actor_id: str, run_input: dict) -> str:
        """Run an Apify actor and return its dataset results as JSON.

        Billed at $0.005 per call via Metrify. Runs the actor synchronously and
        waits for completion before returning all dataset items.

        Args:
            consumer_api_key: Metrify consumer key (format: ck_...).
            actor_id: Apify actor ID or username/actor-name (e.g. "apify/web-scraper").
            run_input: Dictionary of input parameters for the actor.

        Returns:
            JSON string of the actor's dataset items, or an error message prefixed
            with "Error:".
        """
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

    return apify
