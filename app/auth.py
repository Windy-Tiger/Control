"""
Control — Auth Utilities
JWT token handling, password hashing, and FastAPI dependencies.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext
import jwt

SECRET_KEY = os.getenv("SECRET_KEY", "control-dev-secret-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = int(os.getenv("TOKEN_EXPIRE_HOURS", "72"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode["exp"] = expire
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")


# ── FastAPI Dependencies ────────────────────────────────

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Returns decoded token payload: user_id, tenant_id, role, username, fronteira"""
    return decode_token(credentials.credentials)


def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """Only allows admin users through."""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores")
    return current_user


def require_admin_or_operator(current_user: dict = Depends(get_current_user)) -> dict:
    """Allows admin or operador."""
    if current_user.get("role") not in ("admin", "operador"):
        raise HTTPException(status_code=403, detail="Acesso restrito")
    return current_user
