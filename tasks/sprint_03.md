# Sprint 03 — OpenAI + Stability AI + Metering genérico validado
**Semanas:** 3-4 | **GitHub Project column:** Sprint 03  
**Objetivo:** El patrón de metering está probado con 3 types de unidad distintos (tokens, imágenes). El gateway ya no es un wrapper de Anthropic — es un gateway real.

**Estado general:** `[x]` Completo — 56/56 tests passing

---

## Tareas

### TASK-13 · OpenAI wrapper
**Issue GitHub:** #13  
**Estado:** `[x]`  
**Criterio de done:** `OpenAIWrapper(BaseMCPWrapper)` con cálculo de costo per-token compatible con pricing de OpenAI. Misma interfaz que Anthropic. Tests con mock.  
**Commit:** `feat: openai wrapper`

---

### TASK-14 · Stability AI wrapper (per-image)
**Issue GitHub:** #14  
**Estado:** `[x]`  
**Criterio de done:** `StabilityWrapper(BaseMCPWrapper)`. Costo por imagen según modelo (SDXL vs SD3). El "uso real" post-call es binario: 1 imagen generada o 0 si error. Tests con mock.  
**Commit:** `feat: stability ai wrapper (per-image billing)`

---

### TASK-15 · Router — selección dinámica de wrapper
**Issue GitHub:** #15  
**Estado:** `[x]`  
**Criterio de done:** El endpoint `/mcp/call` acepta `{"tool": "anthropic"|"openai"|"stability", "params": {...}}` y despacha al wrapper correcto. Error claro si tool no existe. Tests de routing.  
**Commit:** `feat: tool router with dynamic dispatch`

---

### TASK-16 · Rate limiting básico
**Issue GitHub:** #16  
**Estado:** `[x]`  
**Criterio de done:** Límite de X requests por minuto por wallet (configurable via env var). Respuesta 429 con `Retry-After` header si se supera. Usar slowapi o implementación simple con Redis o in-memory.  
**Commit:** `feat: rate limiting per wallet`

---

## Definición de "Sprint 03 completo"

- [x] Puedo llamar OpenAI, Anthropic y Stability AI desde el mismo endpoint
- [x] Cada tool calcula su costo con su propia unidad (tokens / imagen)
- [x] El router despacha correctamente y falla limpiamente si tool no existe
- [x] Rate limiting activo y testeable
