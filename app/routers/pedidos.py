"""
Control — Pedidos Router
Edit request management: create, list, approve, reject.
"""

import json
from typing import List, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.models.database import get_db, Pedido, Viagem, LogEntry, gen_id, utcnow
from app.models.schemas import PedidoLogCreate, PedidoViagemCreate, PedidoOut
from app.auth import get_current_user, require_admin

router = APIRouter(prefix="/pedidos", tags=["pedidos"])


@router.get("/", response_model=List[PedidoOut])
def list_pedidos(
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    query = db.query(Pedido).filter(Pedido.tenant_id == current_user["tenant_id"])
    if status:
        query = query.filter(Pedido.status == status)
    return query.order_by(Pedido.requested_at.desc()).all()


@router.get("/count")
def count_pending(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    count = db.query(Pedido).filter(
        Pedido.tenant_id == current_user["tenant_id"],
        Pedido.status == "pendente"
    ).count()
    return {"count": count}


# ── Create log edit request ─────────────────────────────

@router.post("/log-edit", response_model=PedidoOut)
def create_log_edit_request(
    req: PedidoLogCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    log = db.query(LogEntry).filter(LogEntry.id == req.log_entry_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Entrada de log não encontrada")

    viagem = db.query(Viagem).filter(
        Viagem.id == log.viagem_id,
        Viagem.tenant_id == current_user["tenant_id"]
    ).first()
    if not viagem:
        raise HTTPException(status_code=404, detail="Viagem não encontrada")

    # Check no duplicate pending
    existing = db.query(Pedido).filter(
        Pedido.log_entry_id == req.log_entry_id,
        Pedido.status == "pendente"
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Já existe um pedido pendente para esta entrada")

    pedido = Pedido(
        tenant_id=current_user["tenant_id"],
        viagem_id=viagem.id,
        type="log-edit",
        log_entry_id=req.log_entry_id,
        original_text=log.text,
        proposed_text=req.proposed_text,
        reason=req.reason,
        requested_by=current_user["username"],
        t1=viagem.t1,
        motorista=viagem.motorista,
    )
    db.add(pedido)
    db.commit()
    db.refresh(pedido)
    return pedido


# ── Create viagem edit request ──────────────────────────

@router.post("/viagem-edit", response_model=PedidoOut)
def create_viagem_edit_request(
    req: PedidoViagemCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    viagem = db.query(Viagem).filter(
        Viagem.id == req.viagem_id,
        Viagem.tenant_id == current_user["tenant_id"]
    ).first()
    if not viagem:
        raise HTTPException(status_code=404, detail="Viagem não encontrada")

    existing = db.query(Pedido).filter(
        Pedido.viagem_id == req.viagem_id,
        Pedido.type == "viagem-edit",
        Pedido.status == "pendente"
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Já existe um pedido de edição pendente para esta viagem")

    pedido = Pedido(
        tenant_id=current_user["tenant_id"],
        viagem_id=viagem.id,
        type="viagem-edit",
        changes_json=req.changes_json,
        new_data_json=req.new_data_json,
        reason=req.reason,
        requested_by=current_user["username"],
        t1=viagem.t1,
        motorista=viagem.motorista,
    )
    db.add(pedido)
    db.commit()
    db.refresh(pedido)
    return pedido


# ── Approve ─────────────────────────────────────────────

@router.post("/{pedido_id}/approve", response_model=PedidoOut)
def approve_pedido(
    pedido_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    pedido = db.query(Pedido).filter(
        Pedido.id == pedido_id,
        Pedido.tenant_id == current_user["tenant_id"]
    ).first()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    if pedido.status != "pendente":
        raise HTTPException(status_code=400, detail="Pedido já foi processado")

    viagem = db.query(Viagem).filter(Viagem.id == pedido.viagem_id).first()

    if pedido.type == "log-edit":
        # Apply text change to log entry
        log = db.query(LogEntry).filter(LogEntry.id == pedido.log_entry_id).first()
        if log:
            log.text = pedido.proposed_text
            log.edited_by = current_user["username"]
            log.edited_at = utcnow()

    elif pedido.type == "viagem-edit" and viagem and pedido.new_data_json:
        # Apply field changes
        new_data = json.loads(pedido.new_data_json)
        changes = json.loads(pedido.changes_json) if pedido.changes_json else []

        # DateTime fields need parsing from string
        datetime_fields = {"t1_emissao", "t1_validade", "t1_partida", "t1_chegada", "limite", "saida"}

        for key, val in new_data.items():
            if hasattr(viagem, key):
                if key in datetime_fields and val and isinstance(val, str):
                    try:
                        from datetime import datetime as dt
                        # Handle various formats
                        val_clean = val.replace("Z", "+00:00")
                        parsed = dt.fromisoformat(val_clean)
                        setattr(viagem, key, parsed)
                    except (ValueError, TypeError):
                        setattr(viagem, key, val)
                else:
                    setattr(viagem, key, val)

        viagem.last_update = utcnow()

        diff_text = " | ".join(f'{c["field"]}: "{c["old"]}" → "{c["new"]}"' for c in changes)
        db.add(LogEntry(
            viagem_id=viagem.id,
            user=current_user["username"],
            mov=viagem.movimento or "viagem",
            text=f"✎ Dados alterados (aprovado por {current_user['username']}, pedido de {pedido.requested_by}). Alterações: {diff_text}",
            is_edit=True,
            changes_json=pedido.changes_json,
        ))

    pedido.status = "aprovado"
    pedido.resolved_by = current_user["username"]
    pedido.resolved_at = utcnow()
    db.commit()
    db.refresh(pedido)
    return pedido


# ── Reject ──────────────────────────────────────────────

@router.post("/{pedido_id}/reject", response_model=PedidoOut)
def reject_pedido(
    pedido_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    pedido = db.query(Pedido).filter(
        Pedido.id == pedido_id,
        Pedido.tenant_id == current_user["tenant_id"]
    ).first()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    if pedido.status != "pendente":
        raise HTTPException(status_code=400, detail="Pedido já foi processado")

    pedido.status = "rejeitado"
    pedido.resolved_by = current_user["username"]
    pedido.resolved_at = utcnow()
    db.commit()
    db.refresh(pedido)
    return pedido
