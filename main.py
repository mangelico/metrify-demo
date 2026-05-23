import os
import uvicorn
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from metrify import Metrify

load_dotenv()

m = Metrify()
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
    port = int(os.environ.get("PORT", 8000))
    app = server.streamable_http_app()
    uvicorn.run(app, host="0.0.0.0", port=port)
