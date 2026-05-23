# CLAUDE.md — metrify-demo (Provider de ejemplo para la red Metrify)

> Este archivo es tu contexto completo. Léelo SIEMPRE antes de escribir cualquier línea de código.
> Al terminar cada sesión, actualizá el estado de las tareas en el sprint activo de `tasks/`.

---

## Qué es este proyecto

**metrify-demo** es el primer provider de ejemplo de la red Metrify.

Ya NO es un gateway propio con billing interno. Ahora es un **MCP server provider** que:
- Expone 6 tools via FastMCP
- Delega el billing completamente a **metrify-backend** via el SDK local `metrify/`
- Demuestra el patrón correcto para cualquier provider que quiera unirse a la red

Analogía: como un plugin de Stripe — implementa el SDK de pagos, no el motor de pagos.

---

## Arquitectura — 3 actores

```
Consumer (AI Agent)  →  metrify-demo (provider)  →  metrify-backend (billing)
                               ↓
                        upstream APIs (Anthropic, OpenAI, etc.)
```

Flujo de cada tool call:
```
1. consumer_api_key llega en el primer param de cada tool
2. @m.tool() pre-check → verifica balance en metrify-backend
3. Tool llama la API upstream (Anthropic, OpenAI, etc.)
4. @m.tool() charge → debita al consumer en metrify-backend
5. Resultado retorna al consumer
   Si upstream falla: NO se cobra (charge no se ejecuta)
```

---

## Stack

| Capa | Tecnología |
|---|---|
| MCP Server | FastMCP (mcp>=1.9.0) |
| Billing SDK | `metrify/` (local, llama metrify-backend via httpx) |
| Hosting | Railway — https://web-production-b51ff.up.railway.app |
| Tests | pytest + pytest-asyncio, 31 tests |

---

## Estructura del repo

```
metrify-demo/
  metrify/              ← SDK local del billing
    __init__.py         ← exporta Metrify
    exceptions.py       ← InsufficientBalanceError, GatewayError
    sdk.py              ← Metrify class: _pre_check, _charge, .tool() decorator
  tools/
    __init__.py
    anthropic_tool.py   ← register(server, m) → @server.tool() @m.tool()
    openai_tool.py
    stability_tool.py
    assemblyai_tool.py  ← usa httpx REST (no SDK, incompatible Python 3.8)
    apify_tool.py       ← usa run_in_executor (Python 3.8 compat)
    firecrawl_tool.py   ← usa run_in_executor (Python 3.8 compat)
  main.py               ← FastMCP server, registra las 6 tools, uvicorn
  tests/
    conftest.py         ← mock_server (passthrough) + mock_m (Metrify con _pre_check/_charge mockeados)
    test_anthropic.py   ← 4 tests
    test_openai.py      ← 4 tests
    test_stability.py   ← 4 tests
    test_assemblyai.py  ← 4 tests
    test_apify.py       ← 4 tests
    test_firecrawl.py   ← 4 tests
    test_billing.py     ← 7 tests (verifica el SDK decorator)
  tasks/
    decisions.md
    sprint_07_provider.md  ← este refactor
```

---

## Patrón de cada tool — doble decorator

```python
def register(server, m):
    @server.tool()
    @m.tool(price=0.000065, unit="per_token")
    async def anthropic(consumer_api_key: str, prompt: str, max_tokens: int = 1024) -> str:
        # billing ocurre en @m.tool ANTES y DESPUÉS de este código
        ...
    return anthropic
```

**CRÍTICO:**
- `consumer_api_key` SIEMPRE es el primer parámetro
- `@m.tool` va DEBAJO de `@server.tool()`
- Billing es: pre_check (antes) → upstream call → charge (si upstream OK)
- Si upstream falla → NO se cobra (tool error retorna string, charge no ejecuta)

---

## Las 6 tools — precios

| Tool | Precio | Unidad | Modelo/API |
|---|---|---|---|
| anthropic | 0.000065 | per_token | claude-haiku-4-5 |
| openai | 0.000010 | per_token | gpt-4o-mini |
| stability | 0.002 | per_image | SDXL v1 REST |
| assemblyai | 0.00617 | per_minute | REST API directo |
| apify | 0.005 | per_call | apify-client |
| firecrawl | 0.001 | per_page | firecrawl-py |

---

## Variables de entorno requeridas

```
METRIFY_PROVIDER_KEY   → pk_live_... (autenticación del provider con metrify-backend)
METRIFY_GATEWAY_URL    → https://airy-wholeness-production-fcc4.up.railway.app
ANTHROPIC_API_KEY      → sk-ant-...
OPENAI_API_KEY         → sk-...
STABILITY_API_KEY      → ...
ASSEMBLYAI_API_KEY     → ...
APIFY_API_KEY          → ...
FIRECRAWL_API_KEY      → ...
PORT                   → 8000 (Railway lo setea automáticamente)
```

---

## Convenciones de código

- **Siempre** async/await en todos los handlers
- **Nunca** hardcodear API keys — siempre `os.environ["KEY"]`
- **Nunca** importar `assemblyai` SDK — incompatible con Python 3.8 (usa httpx directo)
- **Siempre** usar `asyncio.get_running_loop().run_in_executor(None, lambda: ...)` para libs sync
- Tests: pytest, 4 casos mínimo por tool (happy path, insufficient, gateway error, api failure)
- Commits: conventional commits (`feat:`, `fix:`, `refactor:`, `test:`)

---

## Cómo retomar después de un reset de contexto

1. Leer este archivo completo
2. Leer `tasks/decisions.md` — decisiones cerradas, no reabrir
3. Leer `tasks/sprint_07_provider.md` — sprint actual
4. Correr `python -m pytest tests/ -v` para verificar que los 31 tests pasen
5. Continuar desde la primera tarea no completada

---

## Lo que NO hacer

- ❌ No agregar FastAPI/SQLAlchemy/Postgres — este repo no tiene base de datos propia
- ❌ No implementar billing propio — todo el billing va via `metrify/sdk.py` → metrify-backend
- ❌ No crear dashboard Jinja2 — era del gateway viejo, eliminado
- ❌ No importar `assemblyai` SDK — usar httpx REST API directo (ver assemblyai_tool.py)
- ❌ No usar `asyncio.to_thread` — Python 3.8 compat: usar `run_in_executor`
- ❌ No usar `str | None` syntax — Python 3.8: usar `Optional[str]`
