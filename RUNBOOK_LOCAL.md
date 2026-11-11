# Siete Academy — cómo probar localmente

Para probar mañana en tu Mac sin Docker, sin Firebase, sin nada externo.

## Pre-requisitos (una vez)

Ya los tienes en tu Mac:
- **Node 24** vía nvm en `~/.nvm/versions/node/v24.13.0/`
- **uv** vía `~/.local/bin/uv` (maneja Python 3.12)

Si por algún motivo no los tienes, los instalas así:

```bash
# Node (usa tu nvm existente)
nvm install 24

# uv
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Arrancar la demo

Desde la raíz del proyecto (`/Users/cesargranda/Documents/Siete Academy/`):

```bash
make demo
```

Esto, en **un solo comando**, hace todo:

1. Crea `backend/.venv` con Python 3.12 si no existe
2. Instala dependencias Python (FastAPI, SQLAlchemy, Celery, Anthropic SDK, …)
3. Instala dependencias Node del frontend
4. Resetea la base SQLite local (`backend/siete_academy.db`)
5. Siembra data rica: 6 usuarios, 1 curso completo con 4 módulos + lecciones, 5 assessments (MCQ, escrita, base de prospección, cold-call, ejercicio equipo), 3 alumnos con progreso distinto, submissions + teacher reviews + AI drafts, candidatos en 4 stages del pipeline, certificado emitido, sesiones Zoom
6. Arranca backend (`uvicorn`) en `:8000` y frontend (`vite`) en `:5173`

La primera vez tarda ~2-3 min (descarga Python 3.12 + Node deps). Las siguientes, ~10 seg.

**Abre:** http://localhost:5173/academy/

## Cómo probar cada rol

En `/academy/login` verás 4 botones de **modo demo**. Cada uno te entra como un rol distinto sin contraseña. El backend acepta ese acceso cuando `APP_ENV=development` y `DEV_AUTH_BYPASS=true`. `make demo` exporta las dos. Si arrancás el backend a mano, exportalas vos; sin `DEV_AUTH_BYPASS=true` el bypass queda apagado y los botones responden 401.

| Rol | Email | Qué probar |
|---|---|---|
| **Admin** | `admin@siete.com` | Aplicaciones (1 submitted, 1 con Claude score), Cohortes (con editor de ventanas + botones abrir/cerrar), Placement (Kanban con 4 candidatos), Analytics |
| **Profesor** | `teacher@siete.com` | Cola de revisiones (1 pendiente de Diego con **borrador Claude** visible solo a ti), calificar con adjunto URL |
| **Alumno** | `student@siete.com` | Dashboard (cohorte en curso), abrir módulo 01 (lecciones con video + quiz MCQ), Feedback (ver tu MCQ auto-calificado) |
| **Reclutador** | `recruiter@siete.com` | Listado de talento (solo ve a Valeria, graduada aprobada) |

**Data rica sembrada:**
- Aplicaciones: Sofía (submitted), Rodrigo (under_review, con Claude score 78)
- Alumnos: Luis (40% progress), Camila (75%), Diego (100% + certificado emitido)
- Candidatos placement: Luis en `applying`, Camila en `siete_interview`, Diego en `siete_test`, Valeria en `approved`
- Sesión en vivo del módulo 1: `https://us06web.zoom.us/j/88888888888?pwd=demo-siete-academy` (link de ejemplo — reemplázalo cuando quieras probar Zoom real)
- Camila tiene una review escrita del profesor con feedback detallado + adjunto URL
- Diego tiene una entrega pendiente con borrador Claude de crítica

## Idiomas

Arriba a la derecha, en el navbar, botones `es · en · pt`. Toda la UI cambia. El contenido del curso está sembrado en los 3 idiomas.

## Detener

`Ctrl+C` en la terminal donde corre `make demo`.

## Resetear data

```bash
make seed
```

Borra `siete_academy.db` y siembra de nuevo.

## Ver tests

```bash
make test            # backend + frontend + e2e
make test-backend    # solo pytest (60 tests)
```

## Limitaciones de esta demo local

Todas documentadas para que sepas qué no probar todavía:

- **Sin Firebase real** → el login es solo por botones demo. En prod se conectará con Google Auth.
- **Sin SMTP** → los emails se loguean (ves `email.stubbed` en consola) pero no se envían.
- **Sin Anthropic API** → los borradores Claude están pre-sembrados (el de Diego), pero submissions nuevos no generan borradores nuevos porque `ANTHROPIC_API_KEY` está vacío. Cuando le pongas una key real, el pipeline se activa solo.
- **Sin Celery real** → tasks corren inline (`task_always_eager=True`). Bueno para demo, no para volumen prod.
- **Videos de lección** son placeholders de YouTube. Cuando subas los reales, se reemplazan por su ID.
- **Zoom link** del seed es ficticio. Cambia el `zoom_url` en `live_sessions` o desde la UI admin.

## Archivos que puedes tocar para personalizar la demo

| Qué querés cambiar | Dónde |
|---|---|
| Usuarios / datos sembrados | `backend/app/scripts/seed.py` |
| Videos de lecciones | `seed.py` línea con `LESSON_VIDEOS = [...]` |
| Preguntas del MCQ | `seed.py` sección `seed_assessments` |
| Link de Zoom | `seed.py` función `seed_live_sessions` |
| Rate limits | `backend/app/core/limiter.py` + decoradores |
| Copia de la UI | `frontend/src/locales/{es,en,pt}/common.json` |

## Si algo falla

1. `make clean && make demo` — tira todo y reconstruye
2. Si el puerto 8000 o 5173 está ocupado: `lsof -i :8000` y mata el proceso
3. Los logs del backend salen en formato humano en dev. Cada request tiene un `rid=<16-chars>` que correlaciona la línea con el `X-Request-ID` que el frontend envía. Si algo se rompe en UI, copia el `rid` y grep en logs backend.
