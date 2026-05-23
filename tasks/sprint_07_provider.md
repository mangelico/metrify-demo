# Sprint 07 — Refactor a Provider de la red Metrify
**Fecha:** Mayo 2026  
**Objetivo:** metrify-demo deja de ser un gateway propio y se convierte en el primer provider de ejemplo de la red Metrify, usando el metrify-sdk para billing automático.

**Estado general:** `[x]` Completado

---

## Qué cambió

### Eliminado
- `src/` — FastAPI app, MeteringService, wrappers custom, billing interno, dashboard Jinja2
- `alembic/` — migraciones de Postgres (este repo ya no tiene DB propia)
- `demo/` — demo script del gateway viejo
- `tests/` — 98 tests del gateway viejo
- `alembic.ini`

### Creado
- `metrify/` — SDK local que implementa el contrato `Metrify.tool()` decorator
  - `exceptions.py` — InsufficientBalanceError, GatewayError
  - `sdk.py` — Metrify class con _pre_check, _charge, .tool() decorator
- `tools/` — 6 tools como funciones independientes con `register(server, m)`
  - `anthropic_tool.py` — claude-haiku-4-5, $0.000065/token
  - `openai_tool.py` — gpt-4o-mini, $0.000010/token
  - `stability_tool.py` — SDXL via REST, $0.002/image
  - `assemblyai_tool.py` — REST API directo (sin SDK), $0.00617/minute
  - `apify_tool.py` — apify-client + run_in_executor, $0.005/call
  - `firecrawl_tool.py` — firecrawl-py + run_in_executor, $0.001/page
- `main.py` — FastMCP server + registra las 6 tools + uvicorn
- `tests/` — 31 tests nuevos (todos verdes)
  - 4 tests por tool × 6 tools = 24 tests
  - 7 tests de billing SDK (test_billing.py)

---

## Tareas

### TASK-PROVIDER-01 · Eliminar código viejo
**Estado:** `[x]`  
**Criterio:** src/, alembic/, demo/ eliminados. Tests viejos eliminados.

### TASK-PROVIDER-02 · Implementar metrify SDK local
**Estado:** `[x]`  
**Criterio:** `from metrify import Metrify` funciona. _pre_check, _charge, .tool() decorator implementados. Dos-fase billing para "no charge on upstream error".

### TASK-PROVIDER-03 · Implementar 6 tools con doble decorator
**Estado:** `[x]`  
**Criterio:** Cada tool tiene `register(server, m)`. Patrón `@server.tool() @m.tool(price, unit)` correcto. consumer_api_key siempre primer param.

### TASK-PROVIDER-04 · main.py con FastMCP
**Estado:** `[x]`  
**Criterio:** `from mcp.server.fastmcp import FastMCP`. server.streamable_http_app() para Streamable HTTP transport. `PORT` env var.

### TASK-PROVIDER-05 · Tests 31+, todos verdes
**Estado:** `[x]`  
**Resultado:** 31/31 passing.  
Casos por tool: happy path, InsufficientBalanceError, GatewayError, upstream API failure (no charge).  
test_billing.py: verifica orden de ejecución (pre_check → fn → charge), consumer_api_key propagation, precios correctos.

### TASK-PROVIDER-06 · CLAUDE.md + decisions.md actualizados
**Estado:** `[x]`  
**Criterio:** CLAUDE.md refleja la nueva arquitectura de provider. decisions.md tiene DEC-010 a DEC-014.

---

## Decisiones tomadas
- DEC-010: metrify-demo → provider de ejemplo (ver decisions.md)
- DEC-011: billing pre-check + post-charge, no billing-first atómico
- DEC-012: assemblyai SDK reemplazado por httpx REST (Python 3.8 compat)
- DEC-013: asyncio.to_thread → run_in_executor (Python 3.8 compat)
- DEC-014: Stability AI precio fijo sdxl en V1

---

## Resultado final

```
31 passed in 1.64s
```

metrify-demo es ahora el provider de referencia para la red Metrify.
Cualquier developer puede forkearlo y adaptarlo con sus propias upstream APIs.
