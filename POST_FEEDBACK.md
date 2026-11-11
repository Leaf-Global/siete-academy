# Post-feedback → Go live

Plan concreto de qué hacemos cuando vuelvas con feedback de los 4 roles.
Tres fases con entregables claros. Estimado total: **~1 semana** de trabajo
humano si tienes los accesos listos.

---

## FASE A · Iterar sobre tu feedback (1-3 días)

Apenas arrancas el nuevo chat, me pasas por rol qué encontraste. Formato
sugerido para que yo lo procese rápido:

```
ADMIN
  ✅ Funciona: [qué te gustó]
  🐛 Bugs: [lo que rompió, con rid si lo tienes]
  ✏️  Copy: [textos a cambiar]
  💡 UX: [cambios de flujo / agregados]

PROFESOR
  ...

ALUMNO
  ...

RECLUTADOR
  ...
```

Yo priorizo así (sin preguntarte por cada uno):

- **P0 bugs** → fix inmediato, commit, verifico tests verde
- **Copy / i18n** → batch edit en los 3 idiomas (`locales/{es,en,pt}/common.json`)
- **UX tweaks menores** → los aplico sin debate
- **Features nuevas no planeadas** → te consulto con 2-3 opciones antes

Criterio de salida de Fase A: haces una segunda pasada por los 4 roles y das
✅ sin nuevos P0 bugs.

---

## FASE B · Prep de infra (2-3 días, tú + yo con acceso)

Necesito de ti:

| Cosa | Dónde la consigues | Bloquea |
|---|---|---|
| VPS Hetzner con SSH + Coolify corriendo | panel Hetzner | Deploy |
| Cuenta GitHub con el repo creado | crear `siete-academy` private | Coolify lo clona |
| Firebase project | console.firebase.google.com → New project | Auth real |
| Dominio (o subdominio) ya registrado | Cloudflare DNS / registrador | URL pública |
| SMTP provider (Resend recomendado, gratis 3k/mes) | resend.com | Emails |
| Anthropic API key | console.anthropic.com | AI review |

Mientras tú reúnes accesos, yo **en paralelo**:

- Optimizo Dockerfiles para producción (multi-stage build, non-root user)
- Configuro healthchecks con retries reales
- Aprieto CORS, headers de seguridad (CSP, HSTS, X-Frame-Options)
- Agrego CI de GitHub Actions que corre `make test` antes de cualquier merge
- Escribo un `seed-prod.py` que crea **solo** el primer admin (no datos demo)
- Hago pasada de "senior-frontend audit" sobre lo que ajustemos en Fase A
- Hago pasada de "security-review" sobre todo lo nuevo

Criterio de salida de Fase B: **repo en GitHub**, **5 servicios Coolify
creados pero sin traffic**, **health checks respondiendo**.

---

## FASE C · Go-live (1 día con tus accesos)

Ejecutamos en vivo (tú mirando, yo manejando):

1. **Apuntar DNS** → `app.siete.com` o `siete.com/academy` según decisión
2. **TLS automático** vía Coolify + Let's Encrypt
3. **Migraciones**: `alembic upgrade head` en el servicio `api`
4. **Seed-prod**: crear tu usuario admin en Firebase + promoverlo en la DB
5. **Smoke test**: tú entras y recorres los 4 flujos como usuario real
6. **Cloudflare Worker** para `siete.com/academy/*` si vamos por path-based
7. **Navbar Webflow** → agregar link "Academy"
8. **Monitoreo**: activar UptimeRobot + Sentry SDK en backend y frontend
9. **Primer email de invitación**: te paso una plantilla editable para los
   10-15 aspirantes piloto

Criterio de salida: **tú haces login real con Google desde tu celular y
completas el flujo de aplicación hasta la página de éxito**.

---

## Qué ya está listo y no tocamos (evita pánico de última hora)

- ✅ **60 backend tests + 3 frontend + 2 E2E** corriendo con `make test`
- ✅ **Logging JSON estructurado** con request-id propagado entre front y back
- ✅ **Rate limiting** en endpoints públicos (`/applications` 5/h, `/certificates/verify` 30/min)
- ✅ **Pipeline auditable** de Anthropic — toda llamada persistida en `ai_call_logs`
- ✅ **Schema DB** con 23 tablas + 3 migraciones Alembic + índices
- ✅ **i18n** completo en ES/EN/PT para UI + contenido del curso
- ✅ **4 roles** funcionales con ATS Kanban, AI draft para profesor, feedback
  con adjuntos al alumno, certificado con verificación pública
- ✅ **Dev-auth bypass** está apagado por defecto. Se enciende solo con
  `DEV_AUTH_BYPASS=true` y `APP_ENV=development`. Con staging o production
  el proceso no arranca si el flag queda en true.

---

## Canarios si algo sale raro post-launch

Mantén abierta una pestaña con estos tres:

- `https://<dominio>/api/academy/health` → `{"status":"ok"}` siempre
- UptimeRobot → alerta por email si 2 checks fallan
- Sentry → agrupa errores por usuario; si ves picos es que hay un bug real

Para cualquier error reportado por un piloto, pídeles el código que aparece
en el pie de cualquier pantalla (`rid=...`) y yo lo busco en los logs del
backend — tenemos correlación 1:1 front/back.

---

## Cuándo salimos del piloto y abrimos a más volumen

Criterios objetivos para escalar de cohorte 001 (piloto cerrado) a cohorte
002 (más abierta):

- [ ] Al menos 8 de 15 alumnos completan módulo 1
- [ ] Zero P0 bugs en los últimos 7 días
- [ ] Feedback NPS >= 40 del piloto
- [ ] Al menos 1 colocación exitosa (candidato placed)
- [ ] Costo de Anthropic por alumno estimado (decidir si activar cobro V2)

Si los 5 se cumplen, arrancamos la cohorte 002 con marketing moderado.
Si fallan 2+, reset y segundo piloto.
