import asyncio
import logging
import os
import uvicorn
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from metrify import Metrify

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

m = Metrify(mcp_url="https://web-production-b51ff.up.railway.app/mcp")
server = FastMCP("metrify_demo_mcp")

from tools.anthropic_tool import register as register_anthropic
from tools.openai_tool import register as register_openai
from tools.stability_tool import register as register_stability
from tools.assemblyai_tool import register as register_assemblyai
from tools.apify_tool import register as register_apify
from tools.firecrawl_tool import register as register_firecrawl

register_anthropic(server, m)
register_openai(server, m)
register_stability(server, m)
register_assemblyai(server, m)
register_apify(server, m)
register_firecrawl(server, m)

if __name__ == "__main__":
    try:
        result = asyncio.run(m.register_tools())
        logger.info("register_tools OK: %s", result)
    except Exception as exc:
        logger.warning("register_tools failed (server still starting): %s", exc)

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(server.streamable_http_app(), host="0.0.0.0", port=port)
