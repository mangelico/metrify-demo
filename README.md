# Modelo Gateway — MCP Billing Gateway

> **The payment layer every MCP server will need — before they know they need it.**

Modelo es un gateway de pagos que permite a agentes de IA y developers consumir herramientas (LLMs, imagen, audio, web automation) pagando por uso en USDT — sin gestionar múltiples API keys ni suscripciones mensuales.

**Status:** 🔨 En construcción — C1 MVP (Abril 2026)

---

## ¿Qué resuelve?

Un agente que necesita llamar a Anthropic, generar una imagen con Stability AI y transcribir audio con AssemblyAI hoy tiene que:
- Gestionar 3 API keys distintas
- Manejar 3 sistemas de billing distintos
- Implementar 3 integraciones distintas

Con Modelo: **una wallet USDT, un endpoint, cinco herramientas.**

---

## Quickstart (próximamente)

```bash
# 1. Crear wallet
curl -X POST https://api.modelo.dev/wallets \
  -H "Content-Type: application/json" \
  -d '{"name": "mi-agente"}'

# 2. Top-up balance (manual en V1)
# → Instrucciones en el dashboard

# 3. Llamar una tool
curl -X POST https://api.modelo.dev/mcp/call \
  -H "X-API-Key: mk_live_xxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "anthropic",
    "params": {
      "model": "claude-opus-4-5",
      "messages": [{"role": "user", "content": "Hello"}],
      "max_tokens": 100
    }
  }'
```

---

## Tools disponibles en C1

| Tool | Tipo | Unidad de cobro |
|---|---|---|
| `anthropic` | LLM inference | per-token |
| `openai` | LLM inference | per-token |
| `stability` | Image generation | per-image |
| `assemblyai` | Audio transcription | per-minute |
| `apify` | Web automation | per-run |

**Fee de plataforma:** 5% sobre el costo upstream de cada call.

---

## Stack

Python / FastAPI · PostgreSQL · Railway · Polygon USDT (V2)

---

## Para el agente de código

Si sos Claude Code u otro agente trabajando en este repo: lee `CLAUDE.md` primero. Contiene el contexto completo, las decisiones técnicas tomadas, y el sprint activo.
