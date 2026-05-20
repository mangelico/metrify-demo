# Sprint 05-06 — MCP Protocol + Demo + Pulido público
**Semanas:** 5-6 | **GitHub Project column:** Sprint 05-06  
**Objetivo:** El gateway es un MCP server real. Claude Desktop se conecta y 
ve las 6 tools. El demo script muestra el pipeline autónomo completo. 
Alguien puede encontrarlo, entenderlo y probarlo en 30 minutos sin ayuda.

**Estado general:** `[ ]` Bloqueado hasta completar Sprint 04 ✅

---

## Tareas

### TASK-MCP · Completar protocolo MCP estándar
**Issue GitHub:** #27  
**Estado:** `[x]`  
**Criterio de done:** FastMCP con Streamable HTTP transport. Endpoint POST /mcp 
maneja initialize, tools/list y tools/call con billing completo. Claude Desktop 
puede conectarse con URL remota y ver las 6 tools. Auth via header X-API-Key.
Al menos 4 tests: handshake, tools/list formato, tools/call con billing, 
tools/call balance insuficiente.  
**Commit:** `feat: complete MCP protocol (initialize, tools/list, tools/call)`

---

### TASK-21 · README para humanos y LLMs
**Issue GitHub:** #22  
**Estado:** `[x]`  
**Criterio de done:** README con tagline, qué es en 3 líneas, quickstart en 
5 pasos, configuración Claude Desktop (JSON exacto), tabla de 6 tools con 
precios, ejemplos curl, roadmap en 3 líneas, sección "For LLMs" en texto 
plano para que un agente entienda cómo usarlo sin contexto adicional.  
**Commit:** `docs: comprehensive README for humans and LLMs`

---

### TASK-22 · Demo script — pipeline multimedia autónomo
**Issue GitHub:** #23  
**Estado:** `[x]`  
**Criterio de done:** Script demo/agent_demo.py que corre con 
`python demo/agent_demo.py --url "https://ejemplo.com"`. Pipeline completo:
crea wallet → topup $10 → Firecrawl scrapea URL → Claude resume → 
Stability genera imagen → AssemblyAI narra audio. Imprime balance 
antes/después y detalle de cada débito. Guarda outputs en demo/output/.
Prints con emojis, legible en screen share.  
**Commit:** `demo: multimedia pipeline (firecrawl→claude→stability→assemblyai)`

---

### TASK-23 · Listado en directorios MCP
**Issue GitHub:** #24  
**Estado:** `[ ]`  
**Criterio de done:** Gateway listado en Smithery, Glama, mcp.so, PulseMCP.
Cada listing usa el mismo description del README. Esta tarea la hace el 
founder manualmente una vez que TASK-MCP esté completa.  
**Acción:** Manual — no es código.

---

### TASK-24 · Dashboard pulido para demo
**Issue GitHub:** #25  
**Estado:** `[x]`  
**Criterio de done:** Dashboard con header "Modelo Gateway" + tagline, 
métricas top (wallets/calls/volume/uptime), gráfico de barras por tool 
últimas 24h con Chart.js CDN, transacciones con colores por tool. 
Se ve bien en 1280x720. Tema oscuro mantenido.  
**Commit:** `feat: polished dashboard for demo`

---

### TASK-25 · Docs de deploy
**Issue GitHub:** #26  
**Estado:** `[x]`  
**Criterio de done:** DEPLOY.md con requisitos, pasos fork→Railway→variables→
deploy, lista completa de env vars con descripción, cómo conseguir cada API key,
3 endpoints de verificación, cómo conectar Claude Desktop.  
**Commit:** `docs: complete deployment guide`

---

## Definición de "Sprint 05-06 completo — C1 demo-ready"

- [ ] Claude Desktop se conecta al gateway y ve las 6 tools
- [ ] Demo script corre end-to-end con API keys reales
- [x] README que un agente LLM puede leer y entender cómo conectarse
- [x] Dashboard se ve bien en screen share
- [x] DEPLOY.md permite fork→running en 30 minutos
- [ ] Gateway listado en al menos 2 directorios MCP (manual) — TASK-23
- [ ] 3 personas externas lo probaron sin ayuda

**Verificación producción (2026-05-21):**  
POST /mcp → initialize ✅ · tools/list ✅ · tools/call con billing ✅  
105 tests passing. Pendiente: Claude Desktop manual + listing directorios.

**Siguiente paso post-C1:** Lanzar en Hacker News. Beta privada con 
$5 de crédito para los primeros 10 developers.
