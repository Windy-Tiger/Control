"""
Control — Users Router
User management endpoints (admin only).
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.models.database import get_db, User
from app.models.schemas import UserCreate, UserUpdate, UserOut
from app.auth import get_current_user, require_admin, hash_password

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=List[UserOut])
def list_users(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin)
):
    users = db.query(User).filter(User.tenant_id == current_user["tenant_id"]).all()
    return users


@router.post("/", response_model=UserOut)
def create_user(
    req: UserCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin)
):
    # Check duplicate
    existing = db.query(User).filter(
        User.tenant_id == current_user["tenant_id"],
        User.username == req.username
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Utilizador já existe")

    if req.role == "fronteira" and not req.fronteira:
        raise HTTPException(status_code=400, detail="Seleccione a fronteira")

    user = User(
        tenant_id=current_user["tenant_id"],
        username=req.username,
        password_hash=hash_password(req.password),
        role=req.role,
        fronteira=req.fronteira if req.role == "fronteira" else None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.put("/{user_id}", response_model=UserOut)
def update_user(
    user_id: str,
    req: UserUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin)
):
    user = db.query(User).filter(
        User.id == user_id,
        User.tenant_id == current_user["tenant_id"]
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilizador não encontrado")

    if req.fronteira is not None:
        user.fronteira = req.fronteira
    if req.password:
        user.password_hash = hash_password(req.password)

    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}")
def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin)
):
    user = db.query(User).filter(
        User.id == user_id,
        User.tenant_id == current_user["tenant_id"]
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilizador não encontrado")
    if user.username == "admin":
        raise HTTPException(status_code=400, detail="Não é possível remover o administrador principal")

    db.delete(user)
    db.commit()
    return {"ok": True}
