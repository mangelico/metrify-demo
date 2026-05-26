# decisions.md — Decisiones técnicas cerradas

> Estas decisiones fueron tomadas con contexto estratégico completo.
> El agente NO debe reabrirlas ni cuestionarlas — solo ejecutarlas.

---

## DEC-001 — Stack: Python + FastAPI (no TypeScript)
**Fecha:** Abril 2026  
**Razón:** Lenguaje principal del founder. Ecosistema MCP tiene SDK Python de primera clase. FastMCP simplifica los wrappers.

## DEC-002 — Settlement V1 en Postgres, no on-chain
**Fecha:** Abril 2026  
**Razón:** Founder sin experiencia en Solidity. Meter un smart contract en el critical path del MVP agrega riesgo innecesario. El modelo de datos está diseñado para migración limpia a on-chain en V2 (swap tabla wallets → contrato ERC-20).

## DEC-003 — No charge on upstream error
**Fecha:** Abril 2026  
**Razón:** Política de negocio diferenciadora. xpay y Nevermined la tienen; es lo que early adopters van a esperar. Idempotency keys desde día 1.

## DEC-004 — Fee del 5% plano en V1
**Fecha:** Abril 2026  
**Razón:** Alineado con mercado (xpay cobra 5%, OpenRouter ~5%). Fee tiered por volumen se implementa en V2 cuando haya datos reales de uso.

## DEC-005 — Dashboard con Jinja2, no React
**Fecha:** Abril 2026  
**Razón:** Mínima complejidad de frontend. El dashboard V1 es interno/demo, no producto consumer. React agrega build pipeline innecesario para esta etapa.

## DEC-006 — 6 tools en C1: Anthropic, OpenAI, Stability, AssemblyAI, Apify, Firecrawl
**Fecha:** Abril 2026 — actualizado Mayo 2026  
**Razón:** Cubre 4 tipos de unidad de cobro (per-token, per-image, per-minute, per-run, per-page).
Firecrawl agregado como sexta tool: MCP oficial disponible, pricing per-page limpio,
alto valor demo (URL → markdown para LLM), complementa Apify sin solaparse.
Apify = scraping complejo/async. Firecrawl = extracción rápida de contenido de URL específica.

## DEC-007 — Hosting en Railway
**Fecha:** Abril 2026  
**Razón:** Deploy desde GitHub en minutos. Free tier suficiente para MVP. PostgreSQL incluido. Cero config de infraestructura para solo founder.

## DEC-008 — Auth con API keys propias (no OAuth/JWT)
**Fecha:** Abril 2026  
**Razón:** Suficiente para V1. Los early adopters son developers que están cómodos con API keys. OAuth agrega complejidad sin valor en esta etapa.

## DEC-009 — Rate limiting con slowapi in-memory (no Redis)
**Fecha:** Mayo 2026 — TASK-16  
**Razón:** Redis agrega complejidad innecesaria en V1 con una sola instancia. slowapi in-memory es suficiente para el volumen actual. Revisitar cuando haya múltiples instancias o usuarios reales.

## DEC-010 — metrify-demo pasa de gateway propio a provider de ejemplo
**Fecha:** Mayo 2026 — Sprint 07  
**Razón:** La arquitectura evolucionó: metrify-backend es la plataforma de billing, y metrify-demo demuestra cómo cualquier developer puede crear un provider usando el SDK. El repo gateway (con FastAPI, Postgres, MeteringService propio) quedó obsoleto con este modelo.  
**Consecuencia:** Se eliminó src/, alembic/, demo/, y los 98 tests del gateway. Reemplazados por 31 tests del provider.

## DEC-011 — Billing pre-check + post-charge (no billing-first atómico)
**Fecha:** Mayo 2026 — Sprint 07  
**Razón:** Para honrar "no charge on upstream error", el SDK implementa dos fases: _pre_check (verifica balance antes de llamar upstream) y _charge (debita después de éxito upstream). Si el upstream falla, _charge nunca se ejecuta. Limitación V1: si _charge falla después de upstream OK, el consumer no paga (se loguea para reconciliación manual). Solución V2: idempotency keys + webhook de confirmación.

## DEC-012 — assemblyai SDK no compatible con Python 3.8 → httpx REST directo
**Fecha:** Mayo 2026 — Sprint 07  
**Razón:** assemblyai>=0.30 requiere typing.Annotated (Python 3.9+). El entorno local es Python 3.8.4. Se implementó assemblyai_tool.py usando httpx directo contra la REST API v2 de AssemblyAI. No hay pérdida funcional; la REST API es lo que el SDK wrappea internamente.

## DEC-013 — asyncio.to_thread reemplazado por run_in_executor (Python 3.8 compat)
**Fecha:** Mayo 2026 — Sprint 07  
**Razón:** asyncio.to_thread fue agregado en Python 3.9. Se usa asyncio.get_running_loop().run_in_executor(None, lambda: ...) en tools que envuelven libs síncronas (apify, firecrawl). Mantener este patrón mientras Railway use Python 3.8; migrar a to_thread si se upgradea a 3.9+.

## DEC-014 — Stability AI: precio fijo sdxl en V1, sd3 no soportado
**Fecha:** Mayo 2026 — Sprint 07  
**Razón:** sd3 tiene precio diferente ($0.035 vs $0.002 sdxl). En V1 se usa precio fijo de sdxl para todos los requests. El parámetro `model` existe en la interfaz pero no cambia el precio. V2: pricing dinámico por modelo con lookup table.


## DEC-015 — assemblyai audio_duration: check opcional (campo puede estar ausente)
**Fecha:** Mayo 2026  
**Razón:** La API REST v2 de AssemblyAI incluye `audio_duration` (segundos) en el response de polling cuando `status == "completed"`. Sin embargo, el campo puede faltar en respuestas parciales o en versiones futuras de la API. La validación del límite de 5 min se aplica solo si el campo está presente (`data.get("audio_duration")`). Si ausente, se omite el check y se retorna el texto. Esto es preferible a bloquear transcripciones válidas por un campo opcional.
