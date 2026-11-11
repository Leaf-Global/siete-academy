# Siete Academy — Handoff técnico

Documento-puente para el equipo que va a llevar esto de Fase 0 (demo local) a producción.
Lee **este archivo primero**, luego salta a los docs específicos según lo que toques.

**Estado actual:** Fase A (iteración sobre feedback) ~100%. Fase B (infra prod) 0%. Fase C (go-live) 0%.

---

## Documentos del repo (qué leer cuando)

| Archivo | Cuándo leerlo |
|---|---|
| `HANDOFF.md` (este) | Primero. Mapa de qué hay y qué falta. |
| `RUNBOOK_LOCAL.md` | Primer día. Cómo correr la demo en tu Mac en 2 min. |
| `POST_FEEDBACK.md` | Plan general de 3 fases (A / B / C) y criterios de salida. |
| `NEXT_STEPS_PROD.md` | Runbook concreto con comandos — **léelo cuando empieces Fase B**. |
| `CHANGELOG_FASE_A.md` | Qué se agregó en esta iteración. Útil para entender el "por qué". |
| `CLAUDE.md` | Instrucciones para agentes IA (framework WAT). Irrelevante para humanos. |

---

## TL;DR de arquitectura

- **Monorepo** con dos apps:
  - `backend/` — Python 3.12 + FastAPI + SQLAlchemy 2 + SQLite (dev) / Postgres (prod).
  - `frontend/` — React 18 + Vite + TypeScript + Tailwind + react-i18next.
- **Modularidad estricta** en backend: cada concepto es un módulo Python en `backend/app/modules/<nombre>/` con `models.py`, `schemas.py`, `services.py`, `router.py`, `tasks.py` opcional. Todo router se registra en `backend/app/main.py`.
- **Frontend por rol**: cuatro roles (`admin`, `teacher`, `student`, `recruiter`). Rutas protegidas vía `ProtectedRoute`. Layout común en `components/Layout.tsx`.
- **i18n**: 3 locales (`es/en/pt`) en `frontend/src/locales/*/common.json`. Cualquier string de UI debe usar `t("key")`.
- **Request ID propagado** front→back via header `X-Request-ID`. Todo log backend lleva `rid=<16-chars>` para correlación.
- **Tests**: `make test` corre pytest + vitest + playwright. 60+ tests backend.

**Detalles por capa → ver CLAUDE.md (framework) + código directo.**

---

## Módulos backend — endpoints registrados

Todos están en `backend/app/modules/` y registrados en `backend/app/main.py`. Tabla para orientarte rápido:

| Módulo | Prefijo | Qué gestiona |
|---|---|---|
| `auth` | `/auth` | `GET /me` — identifica al usuario actual |
| `users` | `/users` | `GET /users`, `PATCH /users/me`, `PATCH /users/{id}/role` |
| `applications` | `/applications` | Postulación pública + revisión admin (approve/reject) |
| `cohorts` | `/cohorts` | CRUD cohortes + ventanas de módulo + **slack_invite_url** |
| `courses` | `/courses` | Curso, módulos, lecciones (video/manual), **material de apoyo** |
| `enrollment` | `/enrollment` | Enrolar alumnos en cohortes, mover entre cohortes, progreso de lecciones |
| `assessments` | `/assessments` | CRUD pruebas (5 tipos) + entregas + revisiones del profesor |
| `live_sessions` | `/live-sessions` | Zoom URLs por ventana de módulo |
| `placement` | `/placement` | ATS Kanban para colocar graduados |
| `certificates` | `/certificates` | Emisión + verificación pública (`/verify/{code}`) |
| `teacher` | `/teacher` | Dashboard enriquecido + **comentarios directos** al alumno |
| `ai_review` | `/ai-review` | Integración Anthropic Claude (scoring + borradores) |
| `audit` | — | Logs de cambios de stage en placement (usado internamente) |
| `notifications` | — | Servicio `send_email` (SMTP con fallback a stub) |

Lista completa de rutas: `grep -rn "@router\.\(get\|post\|patch\|delete\|put\)" backend/app/modules/`.

---

## Decisiones de diseño que NO debes regresar por accidente

1. **El bypass de auth está apagado por defecto** (`DEV_AUTH_BYPASS=false`). Se enciende solo con `DEV_AUTH_BYPASS=true` y `APP_ENV=development`. Si el flag queda en true con `APP_ENV` `staging` o `production`, `Settings` rechaza la config y el proceso no arranca. `get_current_user` además exige `dev_auth_bypass_active` antes de aceptar `X-Dev-User`. No quites ninguna de las dos comprobaciones. Para prod real, integra Firebase Auth según `NEXT_STEPS_PROD.md` sección 2.

2. **Archivos se almacenan como URLs, no uploads propios.** Material de apoyo, adjuntos de comentarios, adjuntos de reviews del profesor, videos de lecciones — todo es `url: str`. El embed inline usa iframes (YouTube `-nocookie` embed; Drive/PDF viewers externos). Si agregan upload real:
   - Añadan `POST /uploads` en un módulo nuevo (p. ej. `storage`)
   - Usen `fastapi.UploadFile` con límite razonable (50-200 MB)
   - Guarden en bucket externo (S3 recomendado), no en disco del contenedor
   - Persistan solo la URL resultante — los modelos actuales no cambian

3. **Email está stubbed en dev.** `backend/app/modules/notifications/services.py` loguea `email.stubbed` si `SMTP_HOST` no está configurado. Con Resend / Postmark / Gmail SMTP, basta con setear env vars; no hay que tocar código.

4. **Celery corre inline** (`task_always_eager=True` en `backend/app/core/celery.py`). Para prod real, levanten Redis + worker Celery + beat.

5. **Schema se crea via `Base.metadata.create_all`** en arranque de app + seed. Para prod, pásenlo a Alembic (3 migraciones iniciales ya existen en `backend/alembic/versions/` según el README). Cualquier modelo nuevo del Fase A necesita migración nueva antes de deploy.

6. **Lecciones tienen `kind: video | reading`.** Video = YouTube ID embebido. Reading = markdown inline renderizado con CSS `user-select: none` + `@media print { display: none }`. No se pueden descargar. Este es requisito del cliente — no lo cambien "para ser consistentes con material de apoyo".

7. **Material de apoyo sí abre en nueva pestaña**, no embedded. Es intencional: son referencias externas, no parte del flujo.

8. **Certificado se emite manualmente** desde el dashboard del profesor (o admin) cuando el alumno llega a 100% de progreso. Dispara email stub al emitir. **No hay emisión automática al 100%** — se decidió dejar control humano en Fase 0. Si quieren automatizarlo en Fase 1, el hook es en `backend/app/modules/enrollment/router.py::update_progress` (cuando `lp.completed_at` se fija y recalculan `progress_pct == 100`).

9. **Slack actualmente es URL-based** (cohorte tiene `slack_invite_url`). Para auto-invitación por email, el hook es `backend/app/modules/enrollment/router.py::_send_welcome_email`. Ahí mismo, cuando tengan `SLACK_BOT_TOKEN` + canal por cohorte, hagan la llamada a `conversations.invite`.

10. **Flujo de aprobación NO crea User ni Enrollment automáticamente.** Hoy el admin aprueba la aplicación (`POST /applications/{id}/review`) y por separado crea el alumno + lo enrola en `/admin/cohorts`. Esto es intencional para Fase 0 (control granular). Si lo quieren unificar, agreguen en `ApplicationReview` un campo opcional `cohort_id` y, en `services.review_application`, si status=approved y cohort_id presente, creen User (si no existe por email) + Enrollment.

11. **El dev-auth bypass ve solamente 6 usuarios sembrados** (`admin`, `teacher`, `student`/Luis, `camila`, `diego`, `recruiter`). Para probar con más, usen seed. Para prod, usen Firebase real.

---

## Frontend — páginas por rol

```
/ ........................... HomePage (landing marketing)
/apply ...................... Formulario de aplicación (público, rate-limited)
/login ...................... 4 botones demo (bypass)
/account .................... Perfil editable (todos los roles)

/student .................... Dashboard (progreso + banner Slack + share)
/student/module/:id ......... Módulo (lecciones + pruebas + material apoyo)
/student/feedback ........... Comentarios del profesor + reviews de entregas
/student/calendar ........... Sesiones en vivo + ventanas + grabaciones
/student/certificate ........ Certificado del alumno (legacy, no está en nav)

/teacher .................... Dashboard con cohortes + tabla de alumnos
/teacher/reviews ............ Cola de revisiones con búsqueda + filtros

/admin ...................... Panel con 5 atajos
/admin/applications ......... Revisar aplicantes (approve/reject)
/admin/course ............... Editor de curso (módulos, lecciones, pruebas, material)
/admin/cohorts .............. Crear cohortes + editar fechas + asignar alumnos + Slack URL
/admin/placement ............ ATS Kanban para colocación
/admin/analytics ............ Métricas del programa

/recruiter .................. Lista de talento aprobado + botón agendar entrevista
```

---

## Temas estéticos (rebrand 2026)

Los tokens en `frontend/tailwind.config.js` son **semánticos** — no renombren `ember`/`sky`/`bone`/etc. aunque apunten a colores distintos al nombre. Cambiarlos romperá docenas de componentes que usan `bg-ember`, `text-ink`, etc.

**Paleta actual** (matcheada al CSS real de wearesiete.com):
- `#000` `ink` texto principal
- `#F5F5F7` `paper` background
- `#007AFF` `ember` accent / CTAs (System Blue)
- `#8FBDFF` `sky` accent suave (Glacial Sky)
- `#DBDBDB` `bone` borders
- `#5D6C7B` `ink.muted`
- `#999FAE` `ink.faint`

**Fonts:** Montserrat (300-900) para todo + JetBrains Mono para labels. Cargado de Google Fonts en `frontend/index.html`.

**Botones:** pill-shape (`rounded-full`) — matchea `border-radius: 33px` del site en producción. El cambio está en `frontend/src/components/ui/button.tsx`.

Si quieren restaurar el viejo look (serif Fraunces + terracota), hay commit `f2cee3b` y anteriores con el estilo previo — pero no lo hagan sin hablar con Comercial, el rebrand fue pedido explícito.

---

## Fase B — lo que falta para tener login real

Referencia primaria: `NEXT_STEPS_PROD.md`. Resumen de qué integra con qué:

### Auth (Firebase)
- **Backend:** `backend/app/modules/auth/dependencies.py` ya tiene stub para validar Firebase ID tokens. Necesita: `FIREBASE_CREDENTIALS_JSON` env var + descomentar la línea que verifica el token real.
- **Frontend:** `frontend/src/lib/firebase.ts` ya tiene la inicialización; necesita las `VITE_FIREBASE_*` env vars.
- Eliminar visibilidad de los 4 botones demo en `/login` cuando `APP_ENV=production`. Ya hay un `if` preparado.

### Emails reales (SMTP)
- Set `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`. Recomendado: Resend (`smtp.resend.com`, puerto 587).
- Sin cambio de código — el fallback a stub sigue funcionando si falta config.

### Anthropic Claude (AI review)
- Set `ANTHROPIC_API_KEY`. En `backend/app/modules/ai_review/`:
  - `tasks.py::score_application_task` — califica aplicaciones
  - `tasks.py::review_submission_task` — genera borrador de feedback para el profesor
- Usan `anthropic.Anthropic(api_key=...)`. Cada llamada se persiste en `ai_call_logs` (tabla ya existe) para auditar costo.

### File uploads (opcional Fase B, necesario para cohorte 002)
- Hoy no existe. Si lo implementan:
  - Módulo nuevo `backend/app/modules/storage/` con `POST /uploads` aceptando `UploadFile`.
  - Validar tipo MIME + tamaño.
  - Subir a S3 (boto3) o volumen persistente en Coolify.
  - Devolver URL pública.
- Los frontends ya tienen inputs URL que el backend podría llenar — minimal change.

### Slack API (Fase 1+)
- Hook: `backend/app/modules/enrollment/router.py::_send_welcome_email`.
- Agregar env vars: `SLACK_BOT_TOKEN`, `SLACK_COHORT_CHANNEL_PREFIX`.
- Por cohorte, pasar el `channel_id` en un campo adicional `Cohort.slack_channel_id`.
- Llamar `conversations.invite` con el email del user → Slack requiere que el user ya exista en el workspace; para usuarios nuevos, usar `users.admin.invite` (requiere plan pagado).

### Deployment (Coolify en Hetzner)
- `NEXT_STEPS_PROD.md` tiene los comandos exactos. 5 servicios Coolify:
  - `api` (FastAPI backend)
  - `web` (Vite build + Caddy)
  - `postgres`
  - `redis`
  - `celery-worker`
- Docker-compose base: `docker-compose.yml` (está en repo, ajustar para prod multi-stage).

---

## Fase C — go-live (1 día con accesos)

Ver `NEXT_STEPS_PROD.md` sección 7 en adelante. Criterio de salida: **el cliente hace login con Google desde su celular y completa el flujo de aplicación hasta la pantalla de éxito**.

---

## Gotchas conocidos

- **Seed borra y recrea SQLite.** `make seed` hace `rm -f backend/siete_academy.db` + `python -m app.scripts.seed`. Si están probando algo persistente en dev, no corran `make seed`.
- **Alembic migrations están en `backend/alembic/versions/`** pero seed usa `Base.metadata.create_all`. Para prod, **no saltarse alembic** — si agregan una columna nueva en modelo y no crean migración, el deploy va a fallar o va a perder esa columna en el siguiente upgrade.
- **El flag `returnObjects: true` está activado globalmente** en `frontend/src/lib/i18n.ts`. Esto permite a `t("key")` devolver arrays/objetos (usado para `home.modules`, `home.stats`, etc.). No lo quiten.
- **Vite proxy rewrite**: en dev, `/api/academy/*` → `http://localhost:8000/*` (configurado en `frontend/vite.config.ts`). En prod, el path `/academy/*` se sirve via Caddy/Coolify; backend no necesita ese prefix porque `root_path` solo se aplica en `APP_ENV != development`.
- **Token de dev-user va en localStorage key `dev_user_email`** + header `X-Dev-User`. Al hacer logout limpia ambos.

---

## Contacto / quién sabe qué

- **Producto / comercial:** César Granda — dueño del rebrand y las decisiones de copy/flow.
- **Qué preguntar a Comercial antes de tocar:**
  - Copy del landing (todo lo que vive en `home.*` de `locales/`).
  - Paleta de colores / fuentes — la decisión actual viene del PDF de rebranding 2026.
  - Flujo de aprobación → enrollment — si quieren unificarlo en un solo paso.

---

## Cómo verificar que no rompiste nada

Antes de cualquier PR:

```bash
make test                # corre pytest + vitest + playwright
make demo                # smoke test manual — entra con los 4 roles y clickea
```

Si el monitor de errores del dev server o la consola del browser muestran algo en rojo, investiga antes de hacer merge. Todo log backend lleva `rid=<16>` — copia ese id y `grep` en los logs de la terminal donde corre `make demo`.
