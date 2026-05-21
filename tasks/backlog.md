# backlog.md — Todo lo que viene después del C1

> Estas tareas NO se tocan hasta que Sprint 05-06 esté completo y el C1 esté demo-ready.
> El agente no debe implementar nada de aquí sin instrucción explícita del founder.

---

## Sprint 07 — Admin Panel (necesario antes de abrir a usuarios reales)

- [ ] **Panel admin con auth separada** — ruta `/admin` protegida, separada del dashboard público
- [ ] **Revocar/rotar API keys** — desde el dashboard, sin tocar DB directamente
- [ ] **Desactivar wallets** — flag `is_active` en tabla wallets, bloquear calls sin borrar historial
- [ ] **Vista de todas las wallets** — tabla paginada con balance, calls, última actividad
- [ ] **Admin token separado** — gestión del `ADMIN_TOKEN` desde UI, no solo env var

> Prerequisito para beta pública. No bloquea el demo C1.

---

## V2 — Post-validación del C1

- [ ] **Polygon USDT on-chain** — migrar tabla wallets a smart contract ERC-20, web3.py integration
- [ ] **On-ramp MoonPay/Transak** — card → USDT sin pasar por CEX
- [ ] **Perplexity API wrapper** — per-query pricing, web search para agentes
- [ ] **Fee tiered por volumen** — reducción automática según uso mensual
- [ ] **Auth dashboard** — login para que cada developer vea solo sus wallets
- [ ] **Webhook notifications** — alertas cuando balance < threshold
- [ ] **SDK Python cliente** — `pip install modelo-sdk` para integrar en agentes

## V3 — SDK para MCP Server Developers

- [ ] **SDK de monetización** — lo que un MCP server integra para cobrar USDT
- [ ] **Agent-as-provider** — agentes que exponen sus propios servicios y cobran USDT
- [ ] **Agentes-como-proveedores marketplace** — registro y discovery de agentes
- [ ] **Wallet física** — master autoriza al agente a gastar en el mundo físico

## Ideas / Explorar

- [ ] **Perplexity como tool** — alta demanda de agentes que necesitan web search
- [ ] **GitHub MCP wrapper** — per-operation billing para operaciones de código
- [ ] **Notion MCP wrapper** — per-operation para bases de conocimiento
- [ ] **Engineering tools (MATLAB, AutoCAD)** — moat de largo plazo, requiere partnerships
