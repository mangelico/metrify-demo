# Sprint 05-06 — Demo-ready: pulido, README para agentes, listado público
**Semanas:** 5-6 | **GitHub Project column:** Sprint 05-06  
**Objetivo:** El gateway está listo para mostrar a early adopters. Alguien puede encontrarlo, entenderlo y probarlo en 30 minutos sin ayuda.

**Estado general:** `[ ]` Bloqueado hasta completar Sprint 04

---

## Tareas

### TASK-21 · README escrito para LLMs y humanos
**Issue GitHub:** #21  
**Estado:** `[ ]`  
**Criterio de done:** README que incluye: qué es, por qué existe, quickstart en <5 pasos, ejemplo de curl para cada tool, tabla de precios (costo upstream + 5% fee), link al dashboard demo. Escrito para que un LLM lo entienda y elija usar el gateway.  
**Commit:** `docs: comprehensive README for humans and LLMs`

---

### TASK-22 · Demo script — agente pagando su propio uso
**Issue GitHub:** #22  
**Estado:** `[ ]`  
**Criterio de done:** Script Python `demo/agent_demo.py` que muestra el ciclo completo: crea wallet → hace top-up → llama 3 tools distintas → imprime balance antes/después. Es el script que se graba para el video de lanzamiento.  
**Commit:** `demo: autonomous agent paying for its own tool usage`

---

### TASK-23 · Listado en directorios MCP
**Issue GitHub:** #23  
**Estado:** `[ ]`  
**Criterio de done:** Gateway listado en: Smithery, Glama, mcp.so, PulseMCP. Cada listing usa el mismo description del README. Esta tarea la hace el founder manualmente.  
**Acción:** Manual — no es código.

---

### TASK-24 · Dashboard V1.5 — pulido para demo
**Issue GitHub:** #24  
**Estado:** `[ ]`  
**Criterio de done:** Dashboard muestra: balance en tiempo real, gráfico de uso por tool (últimas 24h), lista de transacciones con status visual. Se ve bien en una demo screen share.  
**Commit:** `feat: polished dashboard for demo`

---

### TASK-25 · .env.example completo + docs de deploy
**Issue GitHub:** #25  
**Estado:** `[ ]`  
**Criterio de done:** Un developer puede hacer fork del repo y tenerlo corriendo en Railway en <30 minutos siguiendo las instrucciones. Incluir: setup de Railway, variables de entorno, primer top-up, primer call.  
**Commit:** `docs: complete deployment guide`

---

## Definición de "C1 completo — demo-ready"

- [ ] Gateway en Railway respondiendo con uptime >99%
- [ ] Las 5 tools funcionando en producción
- [ ] README que un agente LLM puede leer y entender cómo usar el gateway
- [ ] Demo script grabable que muestra el ciclo autónomo
- [ ] Listado en al menos 2 directorios MCP
- [ ] 3 personas externas lo probaron sin ayuda (dogfooding)

**Siguiente paso post-C1:** Lanzar en Hacker News con el demo. Invitar a 10-20 developers a beta privada con $50 USDT de crédito gratuito.
