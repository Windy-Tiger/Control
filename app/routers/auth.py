"""
Control — Auth Router
Login endpoint that returns JWT token.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.models.database import get_db, User
from app.models.schemas import LoginRequest, LoginResponse, UserOut
from app.auth import verify_password, create_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    # Find user across all tenants (username + tenant combo is unique)
    user = db.query(User).filter(
        User.username == req.username,
        User.active == True
    ).first()

    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Credenciais inválidas")

    token = create_token({
        "user_id": user.id,
        "tenant_id": user.tenant_id,
        "role": user.role,
        "username": user.username,
        "fronteira": user.fronteira,
    })

    return LoginResponse(
        token=token,
        user=UserOut(
            id=user.id,
            username=user.username,
            role=user.role,
            fronteira=user.fronteira,
        )
    )
