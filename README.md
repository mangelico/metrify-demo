# Modelo Gateway

> **The payment layer every MCP server will need — before they know they need it.**

Modelo is a billing gateway for AI agents. Pay for LLMs, image generation, audio transcription, and web automation with a single USDT wallet — no separate API keys, no monthly subscriptions, no surprise bills.

**One wallet. One endpoint. Six tools. Pay per call.**

🔗 **Production:** https://web-production-b51ff.up.railway.app  
📊 **Dashboard:** https://web-production-b51ff.up.railway.app/dashboard

---

## Quickstart — 5 steps

**Step 1** — Get an API key (contact [@mangelico](https://github.com/mangelico) for beta access, or self-host)

**Step 2** — Check your balance
```bash
curl https://web-production-b51ff.up.railway.app/health
```

**Step 3** — Call a tool
```bash
curl -X POST https://web-production-b51ff.up.railway.app/mcp/call \
  -H "X-API-Key: mk_live_YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "anthropic",
    "params": {
      "messages": [{"role": "user", "content": "What is the capital of France?"}],
      "max_tokens": 50
    }
  }'
```

**Step 4** — Check the `X-Balance-Remaining` response header to see your updated balance

**Step 5** — Connect Claude Desktop (see below) to access all 6 tools via the MCP protocol

---

## Connect Claude Desktop

Add this to your Claude Desktop `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "modelo-gateway": {
      "url": "https://web-production-b51ff.up.railway.app/mcp",
      "headers": {
        "X-API-Key": "mk_live_YOUR_KEY"
      }
    }
  }
}
```

After restarting Claude Desktop, all 6 tools will appear in the tools panel. Each call is billed to your wallet automatically.

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

### Tool call (HTTP API)

```bash
POST /mcp/call
Headers: X-API-Key: mk_live_...
Body: {"tool": "...", "params": {...}, "idempotency_key": "optional-uuid"}

Response:
{
  "result": {...},          // upstream response
  "transaction_id": "uuid",
  "cost_usdt": "0.000800",
  "fee_usdt": "0.000040",
  "total_usdt": "0.000840",
  "request_id": "uuid"
}
X-Balance-Remaining: 9.999160
```

### MCP protocol (Claude Desktop / agents)

```bash
POST /mcp
Headers: X-API-Key: mk_live_...
Body: {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
```

### Wallet management (admin only)

```bash
# Create wallet
POST /wallets
Headers: X-Admin-Token: ...
Body: {"agent_id": "my-agent"}

# Top up
POST /wallets/{wallet_id}/topup
Headers: X-Admin-Token: ...
Body: {"amount": 10.0}

# Check balance
GET /wallets/{wallet_id}
```

### Tool examples

**Anthropic (Claude)**
```bash
curl -X POST .../mcp/call -H "X-API-Key: mk_live_..." -d '{
  "tool": "anthropic",
  "params": {
    "messages": [{"role": "user", "content": "Summarize this article: ..."}],
    "max_tokens": 256,
    "system": "Be concise."
  }
}'
```

**Stability AI (image)**
```bash
curl -X POST .../mcp/call -H "X-API-Key: mk_live_..." -d '{
  "tool": "stability",
  "params": {"prompt": "A futuristic city at sunset", "model": "sdxl"}
}'
```

**Firecrawl (web scraping)**
```bash
curl -X POST .../mcp/call -H "X-API-Key: mk_live_..." -d '{
  "tool": "firecrawl",
  "params": {"url": "https://example.com", "formats": ["markdown"]}
}'
```

**AssemblyAI (transcription)**
```bash
curl -X POST .../mcp/call -H "X-API-Key: mk_live_..." -d '{
  "tool": "assemblyai",
  "params": {"audio_url": "https://your-audio-file.mp3"}
}'
```

**Apify (web automation)**
```bash
curl -X POST .../mcp/call -H "X-API-Key: mk_live_..." -d '{
  "tool": "apify",
  "params": {"actor_id": "apify/web-scraper", "run_input": {"startUrls": [...]}}
}'
```

---

## Roadmap

**V1 (now):** 6 tools, USDT billing simulated in Postgres, single-tenant  
**V2:** On-chain settlement via Polygon, tiered fee model, multi-tenant wallets  
**V3:** Any MCP server can plug in to accept USDT payments through Modelo

---

## Self-hosting

See [DEPLOY.md](DEPLOY.md) for full instructions. Short version:

1. Fork this repo
2. Create a Railway project, add a Postgres database
3. Set environment variables (see DEPLOY.md)
4. Connect GitHub → Railway auto-deploys on push
5. Run `POST /health` to verify

---

## For LLMs

If you are an AI agent reading this to understand how to use Modelo Gateway:

WHAT IT IS: Modelo Gateway is an HTTP API and MCP server that lets you call 6 AI tools (Anthropic Claude, OpenAI GPT, Stability AI images, AssemblyAI transcription, Apify web automation, Firecrawl web scraping) through a single billing layer. You pay with USDT from a wallet balance. Each call costs the upstream API price plus 5% platform fee.

HOW TO USE IT (HTTP API):
- You need an API key (format: mk_live_...) passed as X-API-Key header
- Call POST /mcp/call with body: {"tool": "TOOL_NAME", "params": {...}}
- The response includes "result" (the tool output), "total_usdt" (what was charged), and header X-Balance-Remaining
- If balance is insufficient you get HTTP 402. If upstream fails you get HTTP 502 and are NOT charged.

HOW TO USE IT (MCP PROTOCOL):
- The server implements MCP Streamable HTTP at POST /mcp
- Send {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "your-agent", "version": "1.0"}}}
- Then send {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}} to discover all tools
- Call tools with {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "TOOL_NAME", "arguments": {...}}}
- Auth is always via X-API-Key header on every request

TOOL PARAMETERS:
- anthropic: {messages: [{role, content}], max_tokens, model (optional), system (optional)}
- openai: {messages: [{role, content}], max_tokens, model (optional)}
- stability: {prompt, model (sdxl|sd3, default sdxl)}
- assemblyai: {audio_url, language_code (default en)}
- apify: {actor_id, run_input (optional), timeout_secs (optional)}
- firecrawl: {url, formats (default ["markdown"])}

IMPORTANT RULES:
- Never log or expose the API key
- Use idempotency_key in the request body to safely retry calls without double-billing
- The X-Balance-Remaining header tells you the current wallet balance after each call
- Top up by calling POST /wallets/{wallet_id}/topup with X-Admin-Token (admin operation)

BASE URL: https://web-production-b51ff.up.railway.app
