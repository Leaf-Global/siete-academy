from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import get_settings
from app.core.limiter import limiter
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestIDMiddleware
from app.modules.ai_review.router import router as ai_review_router
from app.modules.applications.router import router as applications_router
from app.modules.assessments.router import router as assessments_router
from app.modules.auth.router import router as auth_router
from app.modules.certificates.router import router as certificates_router
from app.modules.cohorts.router import router as cohorts_router
from app.modules.courses.router import router as courses_router
from app.modules.enrollment.router import router as enrollment_router
from app.modules.live_sessions.router import router as live_sessions_router
from app.modules.placement.router import router as placement_router
from app.modules.teacher.router import router as teacher_router
from app.modules.users.router import router as users_router

configure_logging()
log = get_logger("app.main")

settings = get_settings()

app = FastAPI(
    title="Siete Academy API",
    version="0.1.0",
    root_path="/api/academy" if settings.app_env != "development" else "",
)

# Rate limiter hook-up
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Order matters: RequestID first so every log line picks up the rid
app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)


@app.on_event("startup")
async def _startup():
    if settings.dev_auth_bypass_active:
        log.warning(
            "auth.dev_bypass_enabled",
            extra={
                "env": settings.app_env,
                "detail": "X-Dev-User header is accepted for this process.",
            },
        )
    log.info(
        "app.startup",
        extra={"env": settings.app_env, "cors_origins": settings.cors_origins},
    )


@app.on_event("shutdown")
async def _shutdown():
    log.info("app.shutdown")


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok", "env": settings.app_env}


app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(users_router, prefix="/users", tags=["users"])
app.include_router(applications_router, prefix="/applications", tags=["applications"])
app.include_router(cohorts_router, prefix="/cohorts", tags=["cohorts"])
app.include_router(courses_router, prefix="/courses", tags=["courses"])
app.include_router(enrollment_router, prefix="/enrollment", tags=["enrollment"])
app.include_router(assessments_router, prefix="/assessments", tags=["assessments"])
app.include_router(live_sessions_router, prefix="/live-sessions", tags=["live-sessions"])
app.include_router(placement_router, prefix="/placement", tags=["placement"])
app.include_router(certificates_router, prefix="/certificates", tags=["certificates"])
app.include_router(ai_review_router, prefix="/ai-review", tags=["ai-review"])
app.include_router(teacher_router, prefix="/teacher", tags=["teacher"])
