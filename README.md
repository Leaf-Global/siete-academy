# Siete Academy

LMS para formación SDR de Siete. Cohortes híbridas estilo Reforge: 70% on-demand + 30% en vivo.

> **Equipo técnico que recibe el proyecto:** empieza por [`HANDOFF.md`](HANDOFF.md). Luego
> [`RUNBOOK_LOCAL.md`](RUNBOOK_LOCAL.md) para correrlo, [`CHANGELOG_FASE_A.md`](CHANGELOG_FASE_A.md)
> para entender qué se construyó iterando con el cliente, y [`NEXT_STEPS_PROD.md`](NEXT_STEPS_PROD.md)
> para el runbook de ir a prod.

## Stack

- **Backend:** Python 3.12 + FastAPI (monolito modular) + SQLAlchemy + Alembic + Celery + Redis + PostgreSQL
- **Frontend:** React 18 + Vite + TypeScript + Tailwind + ShadCN + i18next
- **Auth:** Firebase Auth (custom claims para roles)
- **AI:** Anthropic Claude (asistencia a profesores, scoring de aplicaciones)
- **Infra:** Hetzner VPS + Coolify + Docker + GitHub

## Estructura

```
.
├── backend/          # FastAPI + Celery
│   ├── app/
│   │   ├── core/     # Config, DB, Firebase, Celery, i18n
│   │   ├── modules/  # Un módulo por dominio (auth, applications, cohorts, ...)
│   │   └── main.py
│   ├── alembic/
│   └── requirements.txt
├── frontend/         # React SPA
│   └── src/
├── tools/            # Scripts Python ad-hoc (framework WAT)
├── workflows/        # SOPs en markdown
├── infra/            # Cloudflare Worker, Nginx configs
├── docker-compose.yml
└── .env.example
```

## Desarrollo local

```bash
cp .env.example .env
# Completar FIREBASE_*, ANTHROPIC_API_KEY, SMTP_*

docker compose up --build
```

- Backend en http://localhost:8000 (docs en /docs)
- Frontend en http://localhost:5173
- Postgres en :5432, Redis en :6379

### Login de demo (opt-in)

El bypass de autenticación (`X-Dev-User`) arranca **apagado**. Los botones de rol en `/login` funcionan cuando el backend tiene las dos variables:

```bash
APP_ENV=development
DEV_AUTH_BYPASS=true
```

`make demo` y `make dev-backend` las exportan. En Docker Compose el default del servicio es `DEV_AUTH_BYPASS=false`; para la demo local poné `DEV_AUTH_BYPASS=true` en `.env`.

Si `DEV_AUTH_BYPASS=true` y `APP_ENV` es `staging` o `production`, el proceso no arranca (API, worker y Alembic). El entorno se lee de `APP_ENV`.

### Migraciones

```bash
docker compose exec api alembic revision --autogenerate -m "descripción"
docker compose exec api alembic upgrade head
```

### Seed inicial

```bash
docker compose exec api python -m app.scripts.seed
```

## Roles

- **admin** — gestiona cohortes, cursos, usuarios, aplicaciones, placement
- **teacher** — revisa entregas, califica, ve cola de pendientes
- **student** — consume contenido, entrega pruebas, asiste a sesiones en vivo
- **recruiter** — (Fase 1) ve candidatos en pipeline de placement

Los roles se asignan como **custom claims** de Firebase. El backend los verifica en cada request.

## Despliegue (producción)

- GitHub → Coolify → Docker (4 servicios: api, worker, frontend, postgres, redis)
- Cloudflare Worker enruta `siete.com/academy/*` → frontend, `siete.com/api/academy/*` → api
- Webflow sigue sirviendo `siete.com/*`

Ver [infra/](infra/) para configs de reverse proxy.

## Fase 0 (piloto mayo 2026)

1 módulo, 1 cohorte, 10-15 alumnos. Revisión manual de aplicaciones, sin IA, sin ATS, sin certificados PDF automáticos.

Ver plan completo en `~/.claude/plans/necesito-que-pienses-como-logical-eagle.md`.
