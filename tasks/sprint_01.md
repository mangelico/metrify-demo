# Sprint 01 — Esqueleto del proyecto
**Semanas:** 1-2 | **GitHub Project column:** Sprint 01  
**Objetivo:** Repo funcionando, Postgres conectado, primer endpoint vivo en Railway. Al final de este sprint el gateway existe y despliega sin explotar.

**Estado general:** `[~]` En progreso — código completo, TASK-05 pendiente de activación en Railway UI

---

## Tareas

### TASK-01 · Inicializar repo y estructura de proyecto
**Issue GitHub:** #1  
**Estado:** `[x]`  
**Criterio de done:** `git push` exitoso, estructura de carpetas en su lugar, CI no explota.
**Commit:** `78b1484` — `chore: init project structure (closes #1)`

```
modelo-gateway/
├── CLAUDE.md
├── README.md
├── .env.example
├── .gitignore
├── requirements.txt
├── tasks/
├── src/
│   ├── main.py          ← FastAPI app entry point
│   ├── config.py        ← settings con pydantic-settings
│   ├── database.py      ← conexión SQLAlchemy async
│   ├── models/
│   │   ├── wallet.py
│   │   └── transaction.py
│   ├── routers/
│   │   └── health.py
│   └── services/
└── tests/
    └── test_health.py
```

**Dependencias:** ninguna  
**Commit esperado:** `chore: init project structure`

---

### TASK-02 · Configuración de entorno y settings
**Issue GitHub:** #2  
**Estado:** `[x]`  
**Criterio de done:** `src/config.py` lee todas las variables de entorno listadas en CLAUDE.md. `.env.example` completo. `python-dotenv` instalado.
**Commit:** `9267eec` — `feat: environment config with pydantic-settings (closes #2)`

Usar `pydantic-settings` para Settings class:
```python
class Settings(BaseSettings):
    database_url: str
    anthropic_api_key: str
    openai_api_key: str
    stability_api_key: str
    assemblyai_api_key: str
    apify_api_token: str
    platform_fee_pct: float = 0.05
    secret_key: str
    
    model_config = SettingsConfigDict(env_file=".env")
```

**Dependencias:** TASK-01  
**Commit esperado:** `feat: environment config with pydantic-settings`

---

### TASK-03 · Modelos de base de datos (SQLAlchemy async)
**Issue GitHub:** #3  
**Estado:** `[x]`  
**Criterio de done:** Tablas `wallets` y `transactions` definidas con SQLAlchemy async. Alembic configurado. Primera migración generada y aplicable.
**Commit:** `1bff40c` — `feat: database models and first alembic migration (closes #3)`

Usar el esquema exacto de CLAUDE.md. Puntos clave:
- `balance_usdt` como `Numeric(18, 6)` — nunca float
- `idempotency_key` con `unique=True` en transactions
- `status` como Enum: `pending`, `completed`, `upstream_error`, `insufficient_balance`
- Indexes en: `wallet_id`, `agent_id`, `idempotency_key`, `created_at`

**Dependencias:** TASK-02  
**Commit esperado:** `feat: database models and first alembic migration`

---

### TASK-04 · Endpoint /health y app base
**Issue GitHub:** #4  
**Estado:** `[x]`  
**Criterio de done:** `GET /health` devuelve `{"status": "ok", "db": "connected", "version": "0.1.0"}`. Tests pasan. App corre localmente con `uvicorn src.main:app`.
**Commit:** `a44b734` — `feat: health endpoint with db connectivity check (closes #4)`

```python
# respuesta esperada
{
  "status": "ok",
  "db": "connected",
  "version": "0.1.0",
  "timestamp": "2026-04-30T..."
}
```

Tests: 2/2 pasando (happy path + DB disconnected error path).

**Dependencias:** TASK-03  
**Commit esperado:** `feat: health endpoint with db connectivity check`

---

### TASK-05 · Deploy en Railway
**Issue GitHub:** #5  
**Estado:** `[~]`  
**Criterio de done:** App desplegada en Railway. `/health` accesible via URL pública. PostgreSQL provisioned en Railway y conectado. Variables de entorno configuradas en Railway dashboard.
**Commit:** `36eb4bc` — `chore: add Procfile and railway.json for Railway deploy (closes #5)`

Pasos pendientes (requieren acción manual del founder):
1. Crear proyecto en Railway desde el repo de GitHub (`mangelico/modelo-gateway`)
2. Agregar PostgreSQL plugin
3. Configurar todas las env vars de `.env.example`
4. Verificar que `/health` responde `{"db": "connected"}` en la URL pública
5. Auto-deploy desde rama `main` ya configurado por Railway por defecto

**Dependencias:** TASK-04  
**Commit esperado:** `chore: add railway.json / Procfile if needed`

---

### TASK-06 · GitHub Project setup
**Issue GitHub:** #6  
**Estado:** `[ ]`  
**Criterio de done:** GitHub Project creado con columnas: `Backlog | Sprint Activo | In Progress | Done`. Issues #1-#20 creados (ver backlog.md). Sprint 01 issues movidos a columna "Sprint Activo".

Columnas del tablero:
- **Backlog** — todo lo que viene
- **Sprint Activo** — tareas del sprint actual
- **In Progress** — lo que el agente está trabajando ahora
- **Done** — completado y commiteado

**Dependencias:** ninguna (hacer en paralelo con TASK-01)  
**Acción:** Esta tarea la hace el founder manualmente en GitHub UI.

---

## Definición de "Sprint 01 completo"

- [x] Repo en GitHub con estructura correcta
- [x] `GET /health` responde con DB conectada (localmente con mock)
- [ ] Deploy funcionando en Railway con URL pública ← pendiente acción manual
- [ ] Alembic migrations aplicadas en Railway ← pendiente deploy
- [ ] GitHub Project con todos los issues cargados ← pendiente acción manual
- [x] Tests del health endpoint pasando (2/2)

**Al completar:** Mover todos los issues a "Done" y comentar en cada uno el commit correspondiente. Luego leer `tasks/sprint_02.md`.
