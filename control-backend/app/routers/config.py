"""
Control — Config Router
Tenant configuration: alert settings, frontier contacts, route baselines.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.models.database import get_db, Config
from app.models.schemas import ConfigUpdate, ConfigOut, FronteiraContactsUpdate, RouteBaselinesUpdate
from app.auth import get_current_user, require_admin

router = APIRouter(prefix="/config", tags=["config"])


def _get_or_create_config(db: Session, tenant_id: str) -> Config:
    cfg = db.query(Config).filter(Config.tenant_id == tenant_id).first()
    if not cfg:
        cfg = Config(tenant_id=tenant_id)
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


@router.get("/", response_model=ConfigOut)
def get_config(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return _get_or_create_config(db, current_user["tenant_id"])


@router.put("/", response_model=ConfigOut)
def update_config(
    req: ConfigUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    cfg = _get_or_create_config(db, current_user["tenant_id"])

    if req.email is not None:
        cfg.email = req.email
    if req.alert_hours is not None:
        cfg.alert_hours = req.alert_hours
    if req.night_start is not None:
        cfg.night_start = req.night_start
    if req.night_end is not None:
        cfg.night_end = req.night_end
    if req.t1_alert_warning_days is not None:
        cfg.t1_alert_warning_days = req.t1_alert_warning_days
    if req.t1_alert_critical_days is not None:
        cfg.t1_alert_critical_days = req.t1_alert_critical_days

    db.commit()
    db.refresh(cfg)
    return cfg


@router.put("/fronteira-contacts", response_model=ConfigOut)
def update_fronteira_contacts(
    req: FronteiraContactsUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    cfg = _get_or_create_config(db, current_user["tenant_id"])
    cfg.fronteira_contacts_json = req.contacts_json
    db.commit()
    db.refresh(cfg)
    return cfg


@router.put("/route-baselines", response_model=ConfigOut)
def update_route_baselines(
    req: RouteBaselinesUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    cfg = _get_or_create_config(db, current_user["tenant_id"])
    cfg.route_baselines_json = req.baselines_json
    db.commit()
    db.refresh(cfg)
    return cfg
