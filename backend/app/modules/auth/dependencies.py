from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.firebase import verify_id_token
from app.core.logging import bind_user_id, get_logger
from app.modules.users.models import User

log = get_logger("app.auth")


class CurrentUser:
    def __init__(self, user: User, claims: dict) -> None:
        self.user = user
        self.claims = claims

    @property
    def role(self) -> str:
        return self.claims.get("role") or self.user.role


def get_current_user(
    authorization: str | None = Header(None),
    x_dev_user: str | None = Header(None, alias="X-Dev-User"),
    db: Session = Depends(get_db),
) -> CurrentUser:
    settings = get_settings()

    # Local demo login via X-Dev-User. `dev_auth_bypass_active` is true only
    # when DEV_AUTH_BYPASS is set and APP_ENV is development. Settings refuses
    # to load if the flag is on in staging or production; this check still
    # runs so a settings object built without validation cannot authenticate.
    if settings.dev_auth_bypass_active and x_dev_user:
        user = db.query(User).filter_by(email=x_dev_user).first()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Dev user '{x_dev_user}' not found. Run `make seed` first.",
            )
        bind_user_id(user.id)
        log.debug("auth.dev_bypass", extra={"email": x_dev_user, "role": user.role})
        return CurrentUser(
            user=user, claims={"role": user.role, "uid": user.firebase_uid, "_dev": True}
        )

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    token = authorization.split(" ", 1)[1]
    try:
        claims = verify_id_token(token)
    except Exception as e:
        log.warning("auth.token_invalid", extra={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {e}"
        ) from e

    uid = claims.get("uid") or claims.get("sub")
    user = db.query(User).filter_by(firebase_uid=uid).first()
    if user is None:
        user = User(
            firebase_uid=uid,
            email=claims.get("email", ""),
            display_name=claims.get("name"),
            role=claims.get("role", "student"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        log.info(
            "auth.user_provisioned",
            extra={"firebase_uid": uid, "email": user.email, "role": user.role},
        )

    bind_user_id(user.id)
    return CurrentUser(user=user, claims=claims)


def require_roles(*roles: str):
    allowed: tuple[str, ...] = tuple(roles)

    def _dep(current: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current.role not in allowed:
            log.warning(
                "auth.forbidden",
                extra={"required_roles": list(allowed), "user_role": current.role},
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {allowed}",
            )
        return current

    return _dep
