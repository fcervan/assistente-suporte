"""Auth JWT local (v1)."""
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from . import config, duckdb_store

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer = HTTPBearer()


def hash_senha(s: str) -> str:
    return pwd.hash(s)


def check_senha(s: str, h: str) -> bool:
    return pwd.verify(s, h)


def token(user: dict) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=config.JWT_MINUTES)
    return jwt.encode(
        {"sub": user["email"], "role": user["role"], "exp": exp},
        config.JWT_SECRET,
        algorithm=config.JWT_ALG,
    )


def atual(creds: HTTPAuthorizationCredentials = Depends(bearer)) -> dict:
    try:
        payload = jwt.decode(creds.credentials, config.JWT_SECRET, algorithms=[config.JWT_ALG])
        user = duckdb_store.get_user_by_email(payload["sub"])
    except (JWTError, KeyError):
        user = None
    if not user:
        raise HTTPException(status_code=401, detail="Não autenticado")
    return user


def admin(user: dict = Depends(atual)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Só admin")
    return user
