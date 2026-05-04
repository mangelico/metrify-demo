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

## DEC-006 — 5 tools en C1: Anthropic, OpenAI, Stability, AssemblyAI, Apify
**Fecha:** Abril 2026  
**Razón:** Cubre 3 tipos de unidad de cobro (per-token, per-image, per-minute, per-run). Apify sobre Browserbase por mayor madurez de API. Perplexity se agrega en V2.

## DEC-007 — Hosting en Railway
**Fecha:** Abril 2026  
**Razón:** Deploy desde GitHub en minutos. Free tier suficiente para MVP. PostgreSQL incluido. Cero config de infraestructura para solo founder.

## DEC-008 — Auth con API keys propias (no OAuth/JWT)
**Fecha:** Abril 2026  
**Razón:** Suficiente para V1. Los early adopters son developers que están cómodos con API keys. OAuth agrega complejidad sin valor en esta etapa.

## DEC-009 — Rate limiting con slowapi in-memory (no Redis)
**Fecha:** Mayo 2026 — TASK-16  
**Razón:** Redis agrega complejidad innecesaria en V1 con una sola instancia. slowapi in-memory es suficiente para el volumen actual. Revisitar cuando haya múltiples instancias o usuarios reales.
