# Deployment Guide — Modelo Gateway

Deploy your own instance on Railway in under 30 minutes.

---

## Requirements

- GitHub account (to fork the repo)
- [Railway](https://railway.app) account (free tier works for testing)
- API keys for the tools you want to enable (see below)
- Python 3.11+ (only needed for local dev)

---

## Steps

### 1. Fork the repository

```
https://github.com/mangelico/modelo-gateway
```

Fork it to your GitHub account. Keep the repo public or private — Railway works with both.

---

### 2. Create a Railway project

1. Go to [railway.app](https://railway.app) → **New Project**
2. Select **Deploy from GitHub repo** → choose your fork
3. Railway auto-detects the `railway.json` config and starts building

---

### 3. Add a PostgreSQL database

In your Railway project:

1. Click **+ New** → **Database** → **PostgreSQL**
2. Once provisioned, go to the Postgres service → **Variables** tab
3. Copy the `DATABASE_URL` value (format: `postgresql://user:pass@host:port/db`)

---

### 4. Set environment variables

In your Railway web service (not the Postgres service), go to **Variables** and add:

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | ✅ | PostgreSQL connection string from step 3 |
| `SECRET_KEY` | ✅ | Random 32+ char string for API key signing |
| `ADMIN_TOKEN` | ✅ | Secret token for admin endpoints (wallet/key creation) |
| `ANTHROPIC_API_KEY` | ✅ | From [console.anthropic.com](https://console.anthropic.com) |
| `OPENAI_API_KEY` | ✅ | From [platform.openai.com/api-keys](https://platform.openai.com/api-keys) |
| `STABILITY_API_KEY` | optional | From [platform.stability.ai](https://platform.stability.ai) |
| `ASSEMBLYAI_API_KEY` | optional | From [assemblyai.com/dashboard](https://www.assemblyai.com/dashboard) |
| `APIFY_API_TOKEN` | optional | From [console.apify.com/settings/integrations](https://console.apify.com/settings/integrations) |
| `FIRECRAWL_API_KEY` | optional | From [firecrawl.dev/app/api-keys](https://www.firecrawl.dev/app/api-keys) |
| `PLATFORM_FEE_PCT` | optional | Platform fee (default: `0.05` = 5%) |
| `RATE_LIMIT_PER_MINUTE` | optional | Requests per API key per minute (default: `60`) |

Generate `SECRET_KEY` and `ADMIN_TOKEN` with:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Note:** Optional tool keys can be left blank. Calls to that tool will fail with an upstream error until the key is set.

---

### 5. Deploy

Railway deploys automatically on every push to `main`. After setting variables:

1. Go to your web service → **Deployments** tab
2. Click **Redeploy** (or push any commit to trigger a deploy)
3. Watch the build logs — the startup command runs migrations then starts the server:
   ```
   alembic upgrade head && uvicorn src.main:app --host 0.0.0.0 --port $PORT
   ```

First deploy takes ~2 minutes (Nixpacks build + DB migration).

---

## Verification

Once deployed, test these three endpoints:

**1. Health check**
```bash
curl https://YOUR-RAILWAY-URL.up.railway.app/health
# Expected: {"status": "ok", "version": "0.1.0"}
```

**2. Create a wallet** (uses your ADMIN_TOKEN)
```bash
curl -X POST https://YOUR-RAILWAY-URL.up.railway.app/wallets \
  -H "X-Admin-Token: YOUR_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "test-agent"}'
# Expected: {"id": "uuid", "agent_id": "test-agent", "balance_usdt": "0.000000"}
```

**3. MCP protocol handshake** (use the API key from step below)
```bash
# First create an API key:
curl -X POST https://YOUR-RAILWAY-URL.up.railway.app/keys \
  -H "X-Admin-Token: YOUR_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"wallet_id": "WALLET_UUID_FROM_ABOVE"}'
# Returns: {"key": "mk_live_...", ...}

# Then test the MCP handshake:
curl -X POST https://YOUR-RAILWAY-URL.up.railway.app/mcp \
  -H "X-API-Key: mk_live_YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0"}}}'
# Expected: {"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "2024-11-05", ...}}
```

---

## Connect Claude Desktop

Once verified, add this to your Claude Desktop `claude_desktop_config.json`:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`  
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "modelo-gateway": {
      "url": "https://YOUR-RAILWAY-URL.up.railway.app/mcp",
      "headers": {
        "X-API-Key": "mk_live_YOUR_KEY"
      }
    }
  }
}
```

Restart Claude Desktop. All 6 tools will appear in the tools panel.

---

## Local development

```bash
git clone https://github.com/YOUR-USERNAME/modelo-gateway
cd modelo-gateway

# Install dependencies
pip install -r requirements.txt

# Copy env file and fill in values
cp .env.example .env

# Start Postgres (Docker or local install)
# Then run migrations:
alembic upgrade head

# Start the server
uvicorn src.main:app --reload

# Run tests
pytest
```

---

## Troubleshooting

**Deploy fails at migration step**
- Check `DATABASE_URL` is set correctly in Railway variables
- Make sure the Postgres service is in the same Railway project

**401 on all endpoints**
- Verify `ADMIN_TOKEN` matches what you're sending in `X-Admin-Token`
- For `X-API-Key` endpoints, make sure you created an API key via `POST /keys`

**502 on tool calls**
- The upstream API key is missing or invalid
- Check the relevant API key in Railway variables (e.g. `ANTHROPIC_API_KEY`)
- You are **not charged** on upstream errors

**Claude Desktop shows no tools**
- Confirm the MCP handshake curl above works
- Make sure `url` in `claude_desktop_config.json` ends with `/mcp` (not `/mcp/call`)
- Restart Claude Desktop after editing the config

**Rate limit exceeded (429)**
- Default is 60 requests/minute per API key
- Increase `RATE_LIMIT_PER_MINUTE` in Railway variables
