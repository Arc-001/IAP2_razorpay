import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.services.auth_tokens import decode_access_token

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=401, detail="not authenticated")
    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail="invalid or expired token") from e

    user = db.get(User, payload["sub"])
    if user is None:
        raise HTTPException(status_code=401, detail="user no longer exists")
    return user


def require_role(*roles: str):
    def _check(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail=f"requires role in {roles}")
        return user

    return _check
