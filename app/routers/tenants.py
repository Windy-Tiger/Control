"""
Control — Tenants Router
Tenant provisioning. Protected by a master API key.
"""

import os
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session

from app.models.database import get_db, Tenant, User, Config
from app.models.schemas import TenantCreate, TenantOut
from app.auth import hash_password

MASTER_KEY = os.getenv("MASTER_API_KEY", "control-master-key-change-me")

router = APIRouter(prefix="/tenants", tags=["tenants"])


def require_master_key(x_master_key: str = Header(...)):
    if x_master_key != MASTER_KEY:
        raise HTTPException(status_code=403, detail="Invalid master key")


@router.get("/", response_model=List[TenantOut], dependencies=[Depends(require_master_key)])
def list_tenants(db: Session = Depends(get_db)):
    return db.query(Tenant).order_by(Tenant.created_at.desc()).all()


@router.post("/", response_model=TenantOut, dependencies=[Depends(require_master_key)])
def create_tenant(req: TenantCreate, db: Session = Depends(get_db)):
    # Check slug uniqueness
    existing = db.query(Tenant).filter(Tenant.slug == req.slug).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Slug '{req.slug}' já existe")

    tenant = Tenant(name=req.name, slug=req.slug)
    db.add(tenant)
    db.flush()

    # Create default admin user
    admin = User(
        tenant_id=tenant.id,
        username=req.admin_username,
        password_hash=hash_password(req.admin_password),
        role="admin",
    )
    db.add(admin)

    # Create default operator
    operator = User(
        tenant_id=tenant.id,
        username="operador",
        password_hash=hash_password("op2024"),
        role="operador",
    )
    db.add(operator)

    # Create default config
    config = Config(
        tenant_id=tenant.id,
        fronteira_contacts_json='{"Luvo":{"nome":"","tel":""},"Noqui":{"nome":"","tel":""},"Tchicolondo":{"nome":"","tel":""},"Santa Clara":{"nome":"","tel":""},"Luau":{"nome":"","tel":""}}',
    )
    db.add(config)

    db.commit()
    db.refresh(tenant)
    return tenant
