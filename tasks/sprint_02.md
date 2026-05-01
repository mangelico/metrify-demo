# Sprint 02 — Auth Layer + Metering + Primera Tool (Anthropic)
**Semanas:** 2-3 | **GitHub Project column:** Sprint 02  
**Objetivo:** Un agente puede llamar Claude a través del gateway y se le debita el balance. El ciclo completo funciona de punta a punta con una sola tool.

**Estado general:** `[ ]` Bloqueado hasta completar Sprint 01

**⚠ No arrancar este sprint hasta que Sprint 01 esté 100% completo.**

---

## Tareas

### TASK-07 · Auth Layer — API key validation
**Issue GitHub:** #7  
**Estado:** `[ ]`  
**Criterio de done:** Middleware que valida `X-API-Key` header. Keys almacenadas hasheadas en DB. Endpoint `POST /keys` para generar nueva key asociada a wallet. Requests sin key válida devuelven 401.

Flujo:
```
Header X-API-Key: mk_live_xxxxx
  → hash(key) → buscar en DB → resolver wallet_id
  → si no existe → 401 {"error": "invalid_api_key"}
  → si existe → inyectar wallet en request state
```

**Commit esperado:** `feat: api key auth middleware`

---

### TASK-08 · Wallet management — crear y consultar
**Issue GitHub:** #8  
**Estado:** `[ ]`  
**Criterio de done:** Endpoints `POST /wallets` (crear), `GET /wallets/{id}` (consultar balance). Top-up manual `POST /wallets/{id}/topup` (solo para testing en V1 — agrega balance directamente en Postgres).

**Commit esperado:** `feat: wallet CRUD and manual topup`

---

### TASK-09 · Metering service — pre y post call
**Issue GitHub:** #9  
**Estado:** `[ ]`  
**Criterio de done:** Servicio genérico `MeteringService` con métodos `check_balance(wallet_id, estimated_cost)` y `debit(wallet_id, actual_cost, idempotency_key)`. Maneja la política "no charge on upstream error". Tests unitarios cubriendo: balance suficiente, balance insuficiente, upstream error (no debita), retry con mismo idempotency_key (no doble débito).

```python
class MeteringService:
    async def check_balance(wallet_id, estimated_cost) -> bool
    async def debit(wallet_id, actual_cost, fee_pct, idempotency_key, tool, status) -> Transaction
    async def get_balance(wallet_id) -> Decimal
```

**Commit esperado:** `feat: metering service with idempotency`

---

### TASK-10 · MCP Wrapper base — patrón genérico
**Issue GitHub:** #10  
**Estado:** `[ ]`  
**Criterio de done:** Clase base `BaseMCPWrapper` que define la interfaz que todos los wrappers implementan. Incluye: método `call()`, estimación de costo pre-call, extracción de uso real post-call, manejo de errores upstream.

```python
class BaseMCPWrapper:
    tool_name: str
    async def estimate_cost(params) -> Decimal
    async def call(params) -> tuple[dict, Decimal]  # (result, actual_cost)
    async def health_check() -> bool
```

**Commit esperado:** `feat: base MCP wrapper interface`

---

### TASK-11 · Anthropic wrapper + endpoint /call
**Issue GitHub:** #11  
**Estado:** `[ ]`  
**Criterio de done:** `AnthropicWrapper(BaseMCPWrapper)` funcionando. Endpoint `POST /mcp/call` que ejecuta el ciclo completo: auth → balance check → Anthropic call → debit → log → response con `X-Balance-Remaining` header. Tests de integración con mock de Anthropic API.

Cálculo de costo:
```python
# Usar precios reales de Anthropic API
input_cost = input_tokens * price_per_input_token
output_cost = output_tokens * price_per_output_token
total = input_cost + output_cost
fee = total * 0.05
```

**Commit esperado:** `feat: anthropic wrapper and /mcp/call endpoint`

---

### TASK-12 · Dashboard V1 — balance y transacciones
**Issue GitHub:** #12  
**Estado:** `[ ]`  
**Criterio de done:** `GET /dashboard` renderiza página HTML (Jinja2) con: balance actual, lista de últimas 20 transacciones, status por tool, indicador de fee cobrado. Sin auth en V1 (agregar en V2).

**Commit esperado:** `feat: basic dashboard with Jinja2`

---

## Definición de "Sprint 02 completo"

- [ ] Puedo crear un wallet via API
- [ ] Puedo top-up el balance manualmente
- [ ] Un script Python puede llamar `/mcp/call` con tool=anthropic y recibir respuesta de Claude
- [ ] El balance se reduce correctamente después del call
- [ ] La transacción queda logueada en DB con fee calculado
- [ ] Un error de Anthropic NO debita el balance
- [ ] El dashboard muestra el estado correcto
