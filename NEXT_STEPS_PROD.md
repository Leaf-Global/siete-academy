# Siete Academy — Next steps para ir live

Este documento es el runbook para pasar de demo local a **producción accesible
en `siete.com/academy`**. Cada paso tiene comandos concretos y entregables
verificables. Orden por dependencias — no saltes etapas.

Tiempo total estimado con todos los accesos en mano: **~6-8 horas** de trabajo
humano + tiempo de espera de DNS/TLS.

---

## 0 · Prerequisitos

Lo que necesito de ti (traelo antes de empezar):

| Cosa | Para qué | Dónde lo obtienes |
|---|---|---|
| SSH al VPS Hetzner | Deploy | Panel Hetzner → Servers → SSH key |
| Coolify admin URL + login | Orquestación | Ya instalado en el VPS (o te ayudo a instalarlo) |
| Repo en GitHub (privado) | Coolify lo clona | Crear `siete-academy` en tu org GitHub |
| Dominio + acceso DNS | `siete.com/academy` routing | Tu proveedor (Cloudflare DNS recomendado) |
| Cuenta Firebase (proyecto nuevo) | Auth real | console.firebase.google.com → New project |
| Cuenta SMTP | Emails transaccionales | Resend (más simple), Postmark o Gmail app password |
| `ANTHROPIC_API_KEY` | AI review de entregas | console.anthropic.com → API Keys |
| Acceso a cuenta Webflow | Editar navbar de `siete.com` | Tu cuenta actual de Webflow |

Si algo falta, lo anotamos en un TODO; no te bloquea el resto.

---

## 1 · Push a GitHub (15 min)

```bash
cd "/Users/cesargranda/Documents/Siete Academy"
git init
git add -A
git commit -m "Initial Siete Academy monorepo — backend + frontend + e2e"
gh repo create siete-academy --private --source=. --remote=origin --push
```

Entregable: repo `https://github.com/<tu-org>/siete-academy` privado.

---

## 2 · Firebase project (30 min)

1. **Crear proyecto** en console.firebase.google.com → `Siete Academy`
2. **Authentication → Sign-in method** → activar `Google` provider
3. **Authentication → Settings → Authorized domains** → agregar:
   - `siete.com`
   - `localhost` (ya está)
4. **Project Settings → Service accounts → Generate new private key** → descarga JSON → lo vas a pegar en Coolify como `FIREBASE_CREDENTIALS_JSON`
5. **Project Settings → General → Your apps → Add Web app** → apunta los valores:

```bash
# Valores para coolify env (frontend):
VITE_FIREBASE_API_KEY=...
VITE_FIREBASE_AUTH_DOMAIN=siete-academy.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=siete-academy
VITE_FIREBASE_STORAGE_BUCKET=...
VITE_FIREBASE_MESSAGING_SENDER_ID=...
VITE_FIREBASE_APP_ID=...
```

**Dev auth bypass:** el default del código, de la imagen y de Compose es `DEV_AUTH_BYPASS=false`. Con `APP_ENV=staging` o `APP_ENV=production`, `DEV_AUTH_BYPASS=true` impide que arranquen la API, el worker y Alembic. En el `.env` del server dejá `DEV_AUTH_BYPASS=false`, `CELERY_ALWAYS_EAGER=false` y `APP_ENV=production`. Un deploy que deje `APP_ENV` sin setear sigue viéndose como `development`; en ese caso el bypass solo se enciende si alguien pone `DEV_AUTH_BYPASS=true`.

**Crear primer admin manualmente:**

```bash
# En Firebase console → Authentication → Users → Add user
# email: tu@siete.com  | password: <temporal>
# Luego, desde el backend, promoverlo a admin:
curl -X PATCH https://siete.com/api/academy/users/1/role \
  -H "Authorization: Bearer <idToken>" \
  -d '{"role": "admin"}'
# (o hacer un pequeño script SQL que marca el primer user como admin)
```

Entregable: Firebase wired, primer admin creado.

---

## 3 · Deploy a Coolify (1-2 horas primera vez)

### 3.1 · Servicios en Coolify

Crear **5 servicios** en un mismo Project Coolify (llamado `siete-academy`):

| Servicio | Tipo | Imagen / Source |
|---|---|---|
| `postgres` | Postgres 16 | template Coolify |
| `redis` | Redis 7 | template Coolify |
| `api` | Docker from Git | repo + `backend/Dockerfile`, port 8000 |
| `worker` | Docker from Git | repo + `backend/Dockerfile`, cmd override: `celery -A app.core.celery_app.celery_app worker --loglevel=info` |
| `frontend` | Docker from Git | repo + `frontend/Dockerfile`, port 5173 (o build estático) |

### 3.2 · Variables de entorno en `api` + `worker`

Pegar en Coolify → Environment variables del servicio:

```env
APP_ENV=production
APP_SECRET_KEY=<generar con openssl rand -hex 32>
PUBLIC_BASE_URL=https://siete.com
ALLOWED_ORIGINS=https://siete.com

DATABASE_URL=postgresql+psycopg://siete:<password>@postgres:5432/siete_academy
REDIS_URL=redis://redis:6379/0

DEV_AUTH_BYPASS=false
CELERY_ALWAYS_EAGER=false

FIREBASE_CREDENTIALS_JSON=<pegar el JSON del service account en una sola línea>
FIREBASE_PROJECT_ID=siete-academy

ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-opus-4-7

SMTP_HOST=smtp.resend.com
SMTP_PORT=587
SMTP_USER=resend
SMTP_PASSWORD=<resend key>
SMTP_FROM="Siete Academy <academy@siete.com>"
```

### 3.3 · Variables del `frontend`

```env
VITE_API_BASE_URL=/api/academy
VITE_FIREBASE_API_KEY=...
VITE_FIREBASE_AUTH_DOMAIN=siete-academy.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=siete-academy
VITE_FIREBASE_STORAGE_BUCKET=...
VITE_FIREBASE_MESSAGING_SENDER_ID=...
VITE_FIREBASE_APP_ID=...
```

### 3.4 · Correr migraciones primera vez

```bash
# Desde Coolify terminal del servicio api:
alembic upgrade head
python -m app.scripts.seed  # opcional: solo si quieres admin/teacher/student de prueba
```

Entregable: los 5 servicios running, `healthcheck /health` devolviendo 200.

---

## 4 · Routing: `siete.com/academy/*` (30-60 min)

La web principal sigue en Webflow. Necesitamos que `siete.com/academy/*`
apunte a Coolify. Tres opciones, elige una:

### Opción A (recomendada) — Cloudflare Workers

1. Poner `siete.com` detrás de Cloudflare (si no lo está ya)
2. Crear un Worker que enrute por path:

```js
export default {
  async fetch(request) {
    const url = new URL(request.url);
    if (url.pathname.startsWith("/academy") || url.pathname.startsWith("/api/academy")) {
      const target = url.pathname.startsWith("/api/academy")
        ? "https://api.siete-coolify.com"
        : "https://app.siete-coolify.com";
      const u = new URL(target + url.pathname + url.search);
      return fetch(u.toString(), {
        method: request.method,
        headers: request.headers,
        body: request.body,
      });
    }
    return fetch(request); // deja pasar a Webflow
  },
};
```

3. Bind al ruta `siete.com/*`

### Opción B — Webflow reverse proxy

Webflow no soporta reverse proxy nativo. Saltar.

### Opción C — Subdominio dedicado (más simple, pero no es `/academy`)

Apuntar DNS `academy.siete.com` → Coolify. Usar este path-style solo si
Cloudflare Worker falla. La única diferencia: todos los links en frontend
pasan de `/academy/...` a `/` y hay que actualizar `App.tsx basename`.

Entregable: navegas a `https://siete.com/academy/` y cae en el frontend de Coolify.

---

## 5 · Agregar link en Webflow (10 min)

Entra al designer de Webflow → Navbar → agregar item:

- **Label:** `Academy`
- **Link:** `/academy`
- **Publish**

Entregable: botón `Academy` visible en la navbar pública de `siete.com`.

---

## 6 · Contenido real (tú + equipo, 1-5 días)

Esta es la verdadera línea crítica para Mayo. El software está listo; lo
que falta es el contenido.

Checklist por módulo (4 módulos × esto):

- [ ] Video principal grabado y subido a YouTube como **unlisted** → copiar el ID
- [ ] Script/transcript del video
- [ ] 2-3 sub-lecciones adicionales si el módulo lo requiere
- [ ] 1 quiz MCQ (~5 preguntas) con respuestas correctas
- [ ] 1 entrega práctica (escrita, base de prospección, cold call o team exercise)
- [ ] Link Zoom de la sesión en vivo al cierre

Editar en admin desde la UI (o vía API/seed). Para el MVP usa
`POST /courses`, `POST /courses/{id}/modules`, `POST /courses/modules/{id}/lessons`
— documentados en `/docs` Swagger.

**Pendiente de construir para este flujo (próximo sprint):**
- UI admin para subir/editar contenido directo (hoy se hace vía API)
- Upload directo de archivos (hoy se pega URL)

---

## 7 · Dominio + TLS (<30 min, pero DNS puede tardar hasta 24h)

1. Cloudflare DNS → `siete.com` ya debe estar apuntando (si Webflow lo sirve ya)
2. Registrar `app.siete-coolify.com` y `api.siete-coolify.com` apuntando a IP Hetzner
3. Coolify activa Let's Encrypt automático en cada servicio
4. Verificar TLS: `curl -I https://siete.com/academy/`

---

## 8 · Primeros aspirantes (piloto 10-15, 1 semana de outreach)

**Antes:**
- [ ] Probaste cada flujo tú mismo en prod con una cuenta real
- [ ] Diseñaste un email de invitación con el link a `siete.com/academy/apply`
- [ ] Alineaste con tu equipo: quién va a calificar las entregas (teacher)

**Durante:**
- Admin rol: revisas aplicaciones diariamente
- Teacher rol: calificas en 48h máximo
- Tú mismo corres las sesiones en vivo al inicio (3h cada una)

---

## 9 · Monitoreo básico (1-2 horas)

Mínimo viable en producción:

- [ ] **Logs:** Coolify ya los agrega. Conectar a Loki+Grafana o simplemente `docker logs -f` durante el piloto
- [ ] **Uptime:** `https://uptimerobot.com` gratis monitoreando `siete.com/academy/api/academy/health`
- [ ] **Errores:** Sentry — añadir SDK al backend y frontend (1 hora)
- [ ] **Rate limit alerts:** revisar logs de `slowapi` para ver si alguien abusa

El código ya emite logs JSON estructurados con `request_id` — cualquier
agregador (Datadog, Loki, ELK) los parsea sin config adicional.

---

## 10 · Plan de rollout

| Semana | Qué hacer |
|---|---|
| 0 (hoy) | Demo local. Tú pruebas los 4 roles y me das feedback |
| 1 | Ajustes basados en feedback. Deploy a Coolify |
| 2 | Subir contenido módulo 1. Invitar 10-15 aspirantes |
| 3 | Cerrar aplicaciones. Empezar cohorte 001 |
| 4-11 | Cohorte corriendo. Ir subiendo módulos 2, 3, 4 en paralelo |
| 12 | Prueba práctica en Siete. Placement de los graduados |

---

## 11 · Riesgos conocidos y qué hacer

| Riesgo | Mitigación |
|---|---|
| Nadie aplica | Email directo a tu red. LinkedIn post. Sin marketing paid en V1 |
| Aspirantes no completan el video | Hacer opcional en V2 si friction alta |
| Carga de contenido se atrasa | Lanzar con solo módulo 1 grabado; grabar el 2 durante la primera ventana |
| Claude API falla | Pipeline degrada silenciosamente (ya probado); profesor califica sin IA |
| Zoom link se cae mid-clase | Link alternativo en descripción del calendario |
| Primer alumno encuentra bug feo | Monitoreo Sentry + puedes hot-fix vía `git push` → Coolify auto-deploy |

---

## 12 · Checklist one-pager para el día del lanzamiento

Imprime esto:

```
[ ] Demo local validada por 4 roles
[ ] Repo en GitHub (privado)
[ ] Firebase project creado, service account JSON en Coolify
[ ] 5 servicios Coolify running (postgres, redis, api, worker, frontend)
[ ] `alembic upgrade head` corrió limpio
[ ] `curl https://siete.com/academy/api/academy/health` = 200
[ ] Link Academy visible en navbar Webflow
[ ] 1 usuario admin real creado y funcionando
[ ] 1 módulo con contenido real (video + quiz + 1 entrega)
[ ] Link Zoom real configurado en la sesión en vivo del módulo 1
[ ] SMTP probado (enviar un email test)
[ ] Sentry capturando errores
[ ] UptimeRobot monitoreando
[ ] Email de invitación a piloto redactado
[ ] Lista de 15 aspirantes identificados
```

---

## 13 · Lo que el proyecto ya deja hecho para facilitar todo esto

- **Dockerfile prod-grade** en `backend/` — ya configurado con `alembic upgrade head && uvicorn`
- **Dockerfile frontend** — builder Node 20 alpine
- **Healthcheck endpoint** `/health` en el backend
- **Logs JSON** estructurados cuando `APP_ENV=production`
- **Request-ID middleware** que propaga trace por toda la request
- **Auditoría Anthropic completa** en `ai_call_logs` — toda llamada registrada
- **Pipeline runs** en `pipeline_runs` + `stage_runs` — cualquier falla visible
- **Rate limits** en endpoints públicos (apply + certificate verify)
- **60 tests backend + 3 frontend + 2 E2E** — pasarán en CI antes de cada deploy
- **Migraciones Alembic** reproducibles — `upgrade head` siempre llega al mismo schema

---

**Cuando estés listo para ejecutar este runbook, dime desde qué paso arrancamos y lo hacemos juntos.** Si me das acceso (SSH + Firebase owner + Cloudflare) lo ejecuto yo contigo mirando.
