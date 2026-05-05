# Sprint 04 — AssemblyAI + Apify + Firecrawl + Error handling robusto
**Semanas:** 4-5 | **GitHub Project column:** Sprint 04  
**Objetivo:** Las 6 tools del C1 están funcionando. El gateway maneja errores de producción sin explotar.

**Estado general:** `[ ]` Bloqueado hasta completar Sprint 03

---

## Tareas

### TASK-17 · AssemblyAI wrapper (per-minute audio)
**Issue GitHub:** #18  
**Estado:** `[ ]`  
**Criterio de done:** `AssemblyAIWrapper(BaseMCPWrapper)`. Costo por minuto de audio transcripto. El "uso real" se extrae de la metadata de respuesta (duración del audio procesado). Tests con mock.  
**Commit:** `feat: assemblyai wrapper (per-minute billing)`

---

### TASK-18 · Apify wrapper (per-run async)
**Issue GitHub:** #19  
**Estado:** `[ ]`  
**Criterio de done:** `ApifyWrapper(BaseMCPWrapper)`. Maneja el patrón async: inicia run → polling de status → resultado. El costo se calcula cuando el run completa (no al inicio). Si el run falla → no charge. Tests con mock del ciclo async.  
**Commit:** `feat: apify wrapper (async per-run billing)`

---

### TASK-18b · Firecrawl wrapper (per-page scraping)
**Issue GitHub:** #17  
**Estado:** `[ ]`  
**Criterio de done:** `FirecrawlWrapper(BaseMCPWrapper)`. Costo por página scrapeada.
El "uso real" post-call es binario: 1 página extraída o 0 si error. Devuelve contenido
en markdown limpio. Tests con mock.  
**Commit:** `feat: firecrawl wrapper (per-page billing)`

---

### TASK-19 · Error handling y logging estructurado
**Issue GitHub:** #20  
**Estado:** `[ ]`  
**Criterio de done:** Todos los errores devuelven JSON estructurado `{"error": "code", "message": "...", "request_id": "..."}`. Logging con `structlog` — cada request loguea: wallet_id, tool, costo, status, latencia. No loguear API keys ni balances en texto plano.  
**Commit:** `feat: structured error handling and logging`

---

### TASK-20 · Tests de integración — ciclo completo
**Issue GitHub:** #21  
**Estado:** `[ ]`  
**Criterio de done:** Test suite que corre el ciclo completo con mocks para las 6 tools: create wallet → topup → call tool → check balance deducted → check transaction logged. Corre en CI (GitHub Actions).  
**Commit:** `test: full integration test suite for all 6 tools`

---

## Definición de "Sprint 04 completo"

- [ ] Las 6 tools responden desde el gateway
- [ ] AssemblyAI cobra por minuto correctamente
- [ ] Apify maneja el ciclo async sin cobrar si falla
- [ ] Todos los errores tienen formato consistente
- [ ] Firecrawl extrae contenido de URL y cobra por página correctamente
- [ ] Test suite completo corriendo en CI
