"""
Control — Viagens Router
Full trip management: CRUD, logs, completion, movement, photos.
"""

import os
import json
import uuid
import shutil
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload

from app.models.database import (
    get_db, Viagem, Veiculo, LogEntry, Photo, gen_id, utcnow
)
from app.models.schemas import (
    ViagemCreate, ViagemUpdate, ViagemOut, MovimentoUpdate,
    LogEntryCreate, LogEntryEdit, LogEntryOut, PhotoOut,
    ConcluirLuandaRequest, ConcluirFronteiraRequest,
)
from app.auth import get_current_user, require_admin

MEDIA_DIR = os.getenv("MEDIA_DIR", "/app/media")

router = APIRouter(prefix="/viagens", tags=["viagens"])


def _viagem_query(db: Session, tenant_id: str):
    return db.query(Viagem).options(
        joinedload(Viagem.veiculos),
        joinedload(Viagem.logs),
    ).filter(Viagem.tenant_id == tenant_id)


def _get_viagem(db: Session, tenant_id: str, viagem_id: str) -> Viagem:
    v = _viagem_query(db, tenant_id).filter(Viagem.id == viagem_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Viagem não encontrada")
    return v


def _add_system_log(db: Session, viagem_id: str, text: str, mov: str = "viagem"):
    log = LogEntry(
        viagem_id=viagem_id,
        user="SISTEMA",
        mov=mov,
        text=text,
    )
    db.add(log)


def _check_auto_close(db: Session, v: Viagem):
    """Auto-close when both Luanda and Fronteira are done."""
    if v.luanda_done and v.fronteira_done and not v.concluido:
        v.concluido = True
        v.last_update = utcnow()
        _add_system_log(db, v.id,
            "✓ Processo encerrado automaticamente — ambas as conclusões registadas (Luanda + Fronteira).")


def _photo_url(photo: Photo, base_url: str = "") -> str:
    return f"{base_url}/viagens/{photo.viagem_id}/photos/{photo.id}/file"


# ── List viagens ────────────────────────────────────────

@router.get("/", response_model=List[ViagemOut])
def list_viagens(
    concluido: Optional[bool] = Query(None),
    fronteira: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    query = _viagem_query(db, current_user["tenant_id"])

    # Frontier users only see their frontier
    if current_user["role"] == "fronteira" and current_user.get("fronteira"):
        query = query.filter(Viagem.fronteira == current_user["fronteira"])

    if concluido is not None:
        query = query.filter(Viagem.concluido == concluido)

    if fronteira:
        query = query.filter(Viagem.fronteira == fronteira)

    viagens = query.order_by(Viagem.criado_em.desc()).all()

    # Text search (server-side)
    if q:
        q_lower = q.lower()
        viagens = [v for v in viagens if q_lower in " ".join(filter(None, [
            v.motorista, v.t1, v.matricula, v.cliente, v.fronteira,
            v.processo, v.bl, v.du, v.consignatario, v.transportador,
            v.carta, v.carga, v.funcionario, v.ref_cliente,
        ])).lower()]

    return viagens


# ── Get single viagem ──────────────────────────────────

@router.get("/{viagem_id}", response_model=ViagemOut)
def get_viagem(
    viagem_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return _get_viagem(db, current_user["tenant_id"], viagem_id)


# ── Create viagem ──────────────────────────────────────

@router.post("/", response_model=ViagemOut)
def create_viagem(
    req: ViagemCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    v = Viagem(
        tenant_id=current_user["tenant_id"],
        t1=req.t1,
        tipo_t1=req.tipo_t1,
        processo=req.processo,
        bl=req.bl,
        du=req.du,
        motorista=req.motorista,
        carta=req.carta,
        telefone=req.telefone,
        whatsapp=req.whatsapp,
        transportador=req.transportador,
        risco=req.risco or "1",
        matricula=req.matricula if req.tipo_t1 == "contentor" else None,
        marca=req.marca if req.tipo_t1 == "contentor" else None,
        carga=req.carga if req.tipo_t1 == "contentor" else None,
        ncontentor=req.ncontentor if req.tipo_t1 == "contentor" else None,
        cliente=req.cliente,
        consignatario=req.consignatario,
        ref_cliente=req.ref_cliente,
        fronteira=req.fronteira,
        funcionario=req.funcionario,
        fiscal_nome=req.fiscal_nome,
        fiscal_tel=req.fiscal_tel,
        saida=req.saida,
        limite=req.limite,
        movimento="viagem",
        custom_fields_json=req.custom_fields_json,
    )
    db.add(v)
    db.flush()  # get the ID

    # Multi-vehicle
    if req.tipo_t1 == "geral" and req.veiculos:
        for vv in req.veiculos:
            db.add(Veiculo(
                viagem_id=v.id,
                matricula=vv.matricula,
                marca=vv.marca,
                carga=vv.carga,
                ncont=vv.ncont,
            ))
        veiculos_desc = ", ".join(vv.matricula for vv in req.veiculos)
    else:
        veiculos_desc = req.matricula or ""

    # System log
    _add_system_log(db, v.id,
        f"Viagem registada por {current_user['username']}. "
        f"Tipo: {req.tipo_t1}. Veículos: {veiculos_desc}.")

    # Optional initial observation
    if req.obs:
        db.add(LogEntry(
            viagem_id=v.id,
            user=current_user["username"],
            mov="viagem",
            text=req.obs,
        ))

    db.commit()
    return _get_viagem(db, current_user["tenant_id"], v.id)


# ── Update viagem data (admin direct / operator request handled in pedidos) ──

@router.put("/{viagem_id}", response_model=ViagemOut)
def update_viagem(
    viagem_id: str,
    req: ViagemUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    v = _get_viagem(db, current_user["tenant_id"], viagem_id)

    field_labels = {
        "motorista": "Motorista", "telefone": "Telefone", "whatsapp": "WhatsApp",
        "carta": "Carta de Condução", "matricula": "Matrícula", "marca": "Marca/Modelo",
        "carga": "Carga", "ncontentor": "Nº Cont.", "transportador": "Transportador",
        "risco": "Grau de Risco", "fronteira": "Fronteira", "cliente": "Cliente",
        "consignatario": "Consignatário", "t1": "T1", "bl": "BL", "du": "DU",
        "processo": "Nr. Processo", "fiscal_nome": "Agente Fiscal",
        "fiscal_tel": "Tel. Fiscal", "limite": "Limite de Chegada",
        "funcionario": "Funcionário",
    }

    changes = []
    update_data = req.model_dump(exclude={"reason"}, exclude_unset=True)

    for field, new_val in update_data.items():
        if field == "reason":
            continue
        old_val = str(getattr(v, field, "") or "")
        new_str = str(new_val) if new_val is not None else ""
        if old_val != new_str and field in field_labels:
            changes.append({"field": field_labels[field], "old": old_val or "—", "new": new_str or "—"})
            setattr(v, field, new_val)

    if not changes:
        raise HTTPException(status_code=400, detail="Nenhuma alteração detectada")

    v.last_update = utcnow()

    diff_text = " | ".join(f'{c["field"]}: "{c["old"]}" → "{c["new"]}"' for c in changes)
    db.add(LogEntry(
        viagem_id=v.id,
        user=current_user["username"],
        mov=v.movimento or "viagem",
        text=f"✎ Dados alterados por {current_user['username']}. Motivo: {req.reason}. Alterações: {diff_text}",
        is_edit=True,
        changes_json=json.dumps(changes),
    ))

    db.commit()
    return _get_viagem(db, current_user["tenant_id"], v.id)


# ── Movement toggle ────────────────────────────────────

@router.put("/{viagem_id}/movimento")
def update_movimento(
    viagem_id: str,
    req: MovimentoUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    v = _get_viagem(db, current_user["tenant_id"], viagem_id)
    if req.movimento not in ("viagem", "parado"):
        raise HTTPException(status_code=400, detail="Movimento inválido")
    v.movimento = req.movimento
    v.last_update = utcnow()
    db.commit()
    return {"ok": True, "movimento": v.movimento}


# ── Add log entry (update) ─────────────────────────────

@router.post("/{viagem_id}/logs", response_model=LogEntryOut)
def add_log(
    viagem_id: str,
    req: LogEntryCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    v = _get_viagem(db, current_user["tenant_id"], viagem_id)

    log = LogEntry(
        viagem_id=v.id,
        user=current_user["username"],
        mov=req.mov or v.movimento or "viagem",
        text=req.text,
        zona=req.zona,
        contactavel=req.contactavel,
        is_ping=req.is_ping,
    )
    db.add(log)
    v.last_update = utcnow()
    db.commit()
    db.refresh(log)
    return log


# ── Edit log entry (admin only) ────────────────────────

@router.put("/{viagem_id}/logs/{log_id}", response_model=LogEntryOut)
def edit_log(
    viagem_id: str,
    log_id: str,
    req: LogEntryEdit,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    v = _get_viagem(db, current_user["tenant_id"], viagem_id)
    log = db.query(LogEntry).filter(LogEntry.id == log_id, LogEntry.viagem_id == v.id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Entrada não encontrada")

    log.text = req.text
    log.edited_by = current_user["username"]
    log.edited_at = utcnow()
    db.commit()
    db.refresh(log)
    return log


# ── Concluir Luanda ─────────────────────────────────────

@router.post("/{viagem_id}/concluir-luanda")
def concluir_luanda(
    viagem_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    v = _get_viagem(db, current_user["tenant_id"], viagem_id)
    if v.luanda_done:
        raise HTTPException(status_code=400, detail="Luanda já concluído")

    v.luanda_done = True
    v.luanda_done_by = current_user["username"]
    v.luanda_done_at = utcnow()
    v.last_update = utcnow()

    _add_system_log(db, v.id, f"✓ Conclusão Luanda registada por {current_user['username']}.")
    _check_auto_close(db, v)
    db.commit()
    return {"ok": True}


# ── Concluir Fronteira ──────────────────────────────────

@router.post("/{viagem_id}/concluir-fronteira")
def concluir_fronteira(
    viagem_id: str,
    req: ConcluirFronteiraRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    v = _get_viagem(db, current_user["tenant_id"], viagem_id)
    if v.fronteira_done:
        raise HTTPException(status_code=400, detail="Fronteira já concluída")

    v.fronteira_done = True
    v.fronteira_done_at = utcnow()
    v.t1_stamp = req.numero
    v.t1_stamp_date = req.data
    v.t1_stamp_obs = req.obs
    v.last_update = utcnow()

    txt = "✓ Conclusão Fronteira registada."
    if req.numero:
        txt += f" T1 carimbada: {req.numero}"
    if req.obs:
        txt += f" Obs: {req.obs}"
    _add_system_log(db, v.id, txt)
    _check_auto_close(db, v)
    db.commit()
    return {"ok": True}


# ── Reactivar ───────────────────────────────────────────

@router.post("/{viagem_id}/reactivar")
def reactivar(
    viagem_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    v = _get_viagem(db, current_user["tenant_id"], viagem_id)
    v.concluido = False
    v.last_update = utcnow()
    _add_system_log(db, v.id, f"Viagem reactivada por {current_user['username']}.")
    db.commit()
    return {"ok": True}


# ── Delete viagem ───────────────────────────────────────

@router.delete("/{viagem_id}")
def delete_viagem(
    viagem_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    v = _get_viagem(db, current_user["tenant_id"], viagem_id)

    # Delete photo files
    photos = db.query(Photo).filter(Photo.viagem_id == v.id).all()
    for p in photos:
        filepath = os.path.join(MEDIA_DIR, current_user["tenant_id"], p.filename)
        if os.path.exists(filepath):
            os.remove(filepath)

    db.delete(v)
    db.commit()
    return {"ok": True}


# ── Photos ──────────────────────────────────────────────

@router.get("/{viagem_id}/photos", response_model=List[PhotoOut])
def list_photos(
    viagem_id: str,
    instance: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    v = _get_viagem(db, current_user["tenant_id"], viagem_id)
    query = db.query(Photo).filter(Photo.viagem_id == v.id)
    if instance:
        query = query.filter(Photo.instance == instance)
    photos = query.order_by(Photo.created_at).all()

    return [
        PhotoOut(
            id=p.id,
            instance=p.instance,
            filename=p.filename,
            original_name=p.original_name,
            uploaded_by=p.uploaded_by,
            created_at=p.created_at,
            url=_photo_url(p),
        )
        for p in photos
    ]


@router.post("/{viagem_id}/photos", response_model=PhotoOut)
async def upload_photo(
    viagem_id: str,
    instance: str = Query(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    v = _get_viagem(db, current_user["tenant_id"], viagem_id)

    if instance not in ("saida", "viagem", "chegada", "stamp"):
        raise HTTPException(status_code=400, detail="Instance inválida")

    # Save file
    tenant_dir = os.path.join(MEDIA_DIR, current_user["tenant_id"])
    os.makedirs(tenant_dir, exist_ok=True)

    ext = os.path.splitext(file.filename or "photo.jpg")[1] or ".jpg"
    filename = f"{viagem_id}_{instance}_{gen_id()}{ext}"
    filepath = os.path.join(tenant_dir, filename)

    with open(filepath, "wb") as f:
        content = await file.read()
        f.write(content)

    photo = Photo(
        viagem_id=v.id,
        instance=instance,
        filename=filename,
        original_name=file.filename,
        uploaded_by=current_user["username"],
    )
    db.add(photo)
    db.commit()
    db.refresh(photo)

    return PhotoOut(
        id=photo.id,
        instance=photo.instance,
        filename=photo.filename,
        original_name=photo.original_name,
        uploaded_by=photo.uploaded_by,
        created_at=photo.created_at,
        url=_photo_url(photo),
    )


@router.get("/{viagem_id}/photos/{photo_id}/file")
def get_photo_file(
    viagem_id: str,
    photo_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    v = _get_viagem(db, current_user["tenant_id"], viagem_id)
    photo = db.query(Photo).filter(Photo.id == photo_id, Photo.viagem_id == v.id).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Foto não encontrada")

    filepath = os.path.join(MEDIA_DIR, current_user["tenant_id"], photo.filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Ficheiro não encontrado")

    return FileResponse(filepath)


@router.delete("/{viagem_id}/photos/{photo_id}")
def delete_photo(
    viagem_id: str,
    photo_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    v = _get_viagem(db, current_user["tenant_id"], viagem_id)
    photo = db.query(Photo).filter(Photo.id == photo_id, Photo.viagem_id == v.id).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Foto não encontrada")

    filepath = os.path.join(MEDIA_DIR, current_user["tenant_id"], photo.filename)
    if os.path.exists(filepath):
        os.remove(filepath)

    db.delete(photo)
    db.commit()
    return {"ok": True}
