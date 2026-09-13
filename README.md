# Metrify Demo

> **The payment layer every MCP server will need — before they know they need it.**

> **Note:** this repo demonstrates the metrify-sdk in action. For the SDK itself, see [github.com/mangelico/metrify-sdk](https://github.com/mangelico/metrify-sdk)

This is Metrify's dogfooding demo — 6 tools wrapped with the metrify-sdk, showing the full billing loop end to end (agent calls tool → wallet debited → provider credited, automatically).

**One wallet. One endpoint. Six tools. Pay per call.**

🔗 **Production:** https://gateway.metrify.dev

This is Metrify's first real provider on the network — its public display
name in `metrify_list_tools` is **`Metrify-LLM-GW`**. It's a plain MCP
server (FastMCP, `streamable_http_app`), nothing more: every request except
the OAuth metadata endpoint requires `Authorization: Bearer <JWT>`. There
is no separate REST or HTTP API — everything below is the MCP protocol.

---

## Quickstart

**As a consumer, you don't talk to this server directly to get a token.**
Tokens for calling this provider come from **metrify-mcp**, not from here:

1. Get a Metrify consumer account and `ck_live_...` API key, and connect
   `metrify-mcp` to your agent — see
   [metrify-mcp's README](https://github.com/mangelico/metrify-mcp#readme)
   for the (OAuth login) setup.
2. From your agent, call `metrify_approve_provider` with
   `provider_mcp_url = "https://gateway.metrify.dev/mcp"`, then
   `metrify_get_bearer_token` with the same URL. That returns a
   short-lived (1 hour) Bearer JWT scoped specifically to this server.
3. Call this server directly over MCP using that token — see "Connect
   Claude Desktop" and "API Reference" below.

---

## Connect Claude Desktop

This server's token is short-lived and scoped per-provider (see above), so
there's no static, one-time API key to put in a config the way
`metrify-mcp` itself works. Paste the token you got from
`metrify_get_bearer_token` as a Bearer header:

```json
{
  "mcpServers": {
    "metrify-demo": {
      "url": "https://gateway.metrify.dev/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_TOKEN_FROM_METRIFY_GET_BEARER_TOKEN"
      }
    }
  }
}
```

The token expires in 1 hour — you'll need to re-run
`metrify_get_bearer_token` and update this config (or, in autonomous agent
use, skip the static config entirely and call this server's MCP endpoint
directly with a freshly-obtained token each session, the way
`metrify-mcp`'s own "Autonomous Agent Flow" example does).

---

## Tools

| Tool | Description | Unit | Price | + 5% fee |
|---|---|---|---|---|
| `anthropic` | Claude haiku-4-5 LLM | per token | $0.80/M in, $4.00/M out | ✓ |
| `openai` | GPT-4o-mini LLM | per token | $0.15/M in, $0.60/M out | ✓ |
| `stability` | Image generation (SDXL/SD3) | per image | $0.002 (sdxl), $0.035 (sd3) | ✓ |
| `assemblyai` | Audio transcription | per minute | $0.00617/min | ✓ |
| `apify` | Web automation actors | per run | $0.005/run | ✓ |
| `firecrawl` | Web scraping & extraction | per page | $0.001/page | ✓ |

**Platform fee:** 5% on top of upstream cost, calculated post-call on actual usage (never on estimates).  
**No charge on upstream errors** — if the upstream API fails, you are never billed.

---

## API Reference

There is no HTTP/REST API — this server only speaks MCP (Streamable HTTP),
and every request requires a valid Bearer JWT (see "Quickstart" above for
how to get one). The one exception is the public OAuth discovery endpoint:

```bash
GET /.well-known/oauth-protected-resource   # no auth required
```

```json
{
  "resource": "https://gateway.metrify.dev/mcp",
  "authorization_servers": ["https://api.metrify.dev"],
  "bearer_methods_supported": ["header"],
  "resource_documentation": "https://gateway.metrify.dev/docs"
}
```

Everything else goes through the MCP protocol at `POST /mcp`:

```bash
curl -X POST https://gateway.metrify.dev/mcp \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}'
```

then call a tool the same way with
`{"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "...", "arguments": {...}}}`.
A request without a valid Bearer token gets `401` with a `WWW-Authenticate`
header pointing back at the discovery endpoint above; billing failures
(insufficient balance, upstream error, etc.) surface as the MCP tool
result's own error content, not as an HTTP status code.

### Tool parameters

**Anthropic (Claude)** — `{messages: [{role, content}], max_tokens, system (optional)}`
**OpenAI (GPT)** — `{messages: [{role, content}], max_tokens, model (optional)}`
**Stability AI (image)** — `{prompt, model (sdxl|sd3, default sdxl)}`
**AssemblyAI (transcription)** — `{audio_url}`
**Apify (web automation)** — `{actor_id, run_input}`
**Firecrawl (web scraping)** — `{url}`

---

## Roadmap

**V1 (now):** 6 tools, USDT billing simulated in Postgres, single-tenant  
**V2:** On-chain settlement via Polygon, tiered fee model, multi-tenant wallets  
**V3:** Any MCP server can plug in to accept USDT payments through Metrify

---

## Self-hosting

See [DEPLOY.md](DEPLOY.md) for full instructions. Short version:

1. Fork this repo
2. Create a Railway project, add a Postgres database
3. Set environment variables (see DEPLOY.md)
4. Connect GitHub → Railway auto-deploys on push
5. Verify it's up with `GET /.well-known/oauth-protected-resource` (the one
   public, unauthenticated endpoint — see "API Reference" above)

---

## For LLMs

If you are an AI agent reading this to understand how to use Metrify Demo:

WHAT IT IS: Metrify Demo is an MCP server (Streamable HTTP) that lets you call 6 AI tools (Anthropic Claude, OpenAI GPT, Stability AI images, AssemblyAI transcription, Apify web automation, Firecrawl web scraping) through Metrify's billing layer. You pay with USDT from a wallet balance. Each call costs the upstream API price plus 5% platform fee. There is no HTTP/REST API — MCP is the only interface.

HOW TO GET A TOKEN: you do not authenticate to this server directly with an API key. Connect to metrify-mcp first (see its README), then call its `metrify_approve_provider` tool with provider_mcp_url="https://gateway.metrify.dev/mcp", then `metrify_get_bearer_token` with the same URL. That returns a Bearer JWT scoped to this server, valid for 1 hour.

HOW TO USE IT (MCP PROTOCOL):
- POST to https://gateway.metrify.dev/mcp with header Authorization: Bearer <token from metrify_get_bearer_token>
- Send {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "your-agent", "version": "1.0"}}}
- Then send {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}} to discover all tools
- Call tools with {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "TOOL_NAME", "arguments": {...}}}
- A request with no Bearer token, or an expired/wrongly-scoped one, gets HTTP 401 with a WWW-Authenticate header
- Billing failures (insufficient balance, upstream error) come back as the tool call's own error result, not a separate HTTP status

TOOL PARAMETERS:
- anthropic: {messages: [{role, content}], max_tokens, model (optional), system (optional)}
- openai: {messages: [{role, content}], max_tokens, model (optional)}
- stability: {prompt, model (sdxl|sd3, default sdxl)}
- assemblyai: {audio_url, language_code (default en)}
- apify: {actor_id, run_input (optional), timeout_secs (optional)}
- firecrawl: {url, formats (default ["markdown"])}

IMPORTANT RULES:
- Never log or expose your Bearer token
- Tokens expire in 1 hour — call metrify_get_bearer_token again to refresh, don't hardcode one long-term
- No charge on upstream error — if the underlying tool call fails, you are not billed
- To check your wallet balance or spending history, use metrify-mcp's `metrify_get_balance` / `metrify_get_transactions` tools — this server does not expose wallet endpoints itself

BASE URL: https://gateway.metrify.dev
