# CLAUDE.md — Modelo Gateway / MCP Billing Gateway

> Este archivo es tu contexto completo. Léelo SIEMPRE antes de escribir cualquier línea de código.
> Al terminar cada sesión, actualizá el estado de las tareas en `tasks/sprint_actual.md`.

---

## Qué es este proyecto

Un **MCP Billing Gateway** — infraestructura de pagos que permite a agentes de IA y developers consumir herramientas (LLMs, imagen, audio, web automation) pagando por uso en USDT, sin gestionar múltiples API keys ni suscripciones.

Analogía: **Stripe para el ecosistema MCP**. No un gateway de tools — la capa de pagos sobre la que el ecosistema construye.

Tagline: *"The payment layer every MCP server will need — before they know they need it."*

---

## Stack — NO cambiar sin consultar

| Capa | Tecnología | Razón |
|---|---|---|
| Gateway API | Python 3.11 + FastAPI | Stack principal del founder |
| MCP wrappers | FastMCP | SDK oficial MCP en Python |
| Base de datos | PostgreSQL en Railway | Wallets + transactions + audit |
| Hosting | Railway | Deploy desde GitHub, zero config | https://web-production-b51ff.up.railway.app |
| Settlement V1 | Postgres (simulado) | Valida flujo sin Solidity |
| Settlement V2 | web3.py + Polygon | Post-validación del flujo |
| Dashboard | FastAPI + Jinja2 | Simple, sin frontend framework |
| Auth | API keys propias (headers) | Sin OAuth en V1 |

---

## Arquitectura — 4 capas

```
[Consumidores]  AI Agent / Developer  →  Un solo endpoint MCP
      ↓
[Gateway]       Auth → Metering (pre) → Router → MCP Wrapper → Upstream API → Metering (post) → Log
      ↓
[Datos]         Postgres: tabla wallets + tabla transactions + Dashboard
      ↓
[Tools C1]      Anthropic → OpenAI → Stability AI → AssemblyAI → Apify
```

---

## Flujo de una transacción (el ciclo completo)

```
1. Agent POST /mcp/tool/call  {tool: "anthropic", params: {...}}
2. Auth Layer     → valida API key, resuelve wallet_id
3. Metering PRE   → consulta balance, estima costo, rechaza si insuficiente
4. Router         → selecciona MCP wrapper correcto
5. MCP Wrapper    → llama upstream API real
6. Metering POST  → calcula costo exacto (uso real), aplica 5% fee, debita
7. Log            → inserta en tabla transactions con idempotency_key
8. Response       → devuelve resultado + header X-Balance-Remaining
```

---

## Regla crítica de negocio — NO charge on upstream error

Si la upstream API falla después de procesar parte del request:
- **NO se debita nada al agente**
- Se loguea el intento con status `upstream_error`
- Se usa idempotency_key para evitar doble débito en retries
- Esta política es innegociable — es lo que diferencia el producto de competidores

---

## Modelo de datos — tablas principales

```sql
-- wallets
id, agent_id (unique), master_id, balance_usdt (decimal 18,6),
created_at, updated_at
-- top-up V1: POST /wallets/{id}/topup — suma balance directo en Postgres, sin crypto real

-- transactions  
id, wallet_id (FK), tool, upstream_cost, fee_5pct, total_cost,
status (pending|completed|upstream_error|insufficient_balance),
idempotency_key (unique), request_payload (json), response_meta (json),
created_at
```

---

## Las 5 tools del C1 — orden y tipo de unidad

| # | Tool | Unidad de cobro | Sem. objetivo |
|---|---|---|---|
| 1 | Anthropic API | per-token (input+output) | 1-2 | claude-haiku-4-5 |
| 2 | OpenAI API | per-token (input+output) | 2-3 | gpt-4o-mini |
| 3 | Stability AI | per-image | 3 |
| 4 | AssemblyAI | per-minute (audio) | 4 |
| 5 | Apify | per-run (async) | 5 |

---

## Fee model

- **5% platform fee** sobre cada call, encima del costo upstream
- Fee tiered por volumen (implementar en V2, no ahora)
- El fee se calcula post-call sobre el costo real, no el estimado

---

## Convenciones de código

- **Siempre** usar async/await en FastAPI (no sync handlers)
- **Siempre** usar Pydantic v2 para validación de requests/responses
- **Siempre** agregar idempotency_key en cada transacción desde el día 1
- **Nunca** hardcodear API keys — usar variables de entorno via python-dotenv
- **Nunca** loguear valores de API keys o balances en texto plano
- Tests: pytest, al menos happy path + error path por cada wrapper
- Commits: conventional commits (`feat:`, `fix:`, `refactor:`, `test:`)

---

## Variables de entorno requeridas

```
DATABASE_URL=postgresql://...
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
STABILITY_API_KEY=...
ASSEMBLYAI_API_KEY=...
APIFY_API_TOKEN=...
PLATFORM_FEE_PCT=0.05
SECRET_KEY=...  # para signing de API keys internas
```

---

## Cómo retomar después de un reset de contexto

1. Leer este archivo completo
2. Leer `tasks/decisions.md` — decisiones ya cerradas, no reabrir
3. Leer el sprint activo en `tasks/` — buscar tareas `[~]` (en progreso) o `[ ]` (pendientes)
4. Continuar desde la primera tarea no completada
5. Al terminar cada tarea: marcarla `[x]` en el archivo y cerrar el issue de GitHub con `gh issue close <N> --comment "Completado en <commit>"`

---

## GitHub Issues — cómo usarlos

Cada tarea del sprint tiene un issue de GitHub asociado. El agente debe:
- Referenciar el issue en cada commit: `feat: auth layer básico (closes #3)`
- Actualizar el issue con comentario si hay decisiones tomadas en el proceso
- Nunca cerrar un issue sin que el código esté commiteado y los tests pasen

---

## Lo que NO hacer (decisiones ya tomadas, no reabrir)

- ❌ No implementar Solidity / smart contracts en V1
- ❌ No agregar autenticación OAuth o JWT en V1 (API keys propias es suficiente)
- ❌ No crear un frontend React — Jinja2 para el dashboard
- ❌ No agregar Browserbase en C1 — Apify cubre el mismo caso de uso
- ❌ No implementar token nativo — USDT simulado en Postgres V1
- ❌ No optimizar performance antes de tener el flujo completo funcionando
