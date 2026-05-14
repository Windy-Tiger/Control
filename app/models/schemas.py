"""
Control — Pydantic Schemas
Request/response models for the API.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ── Auth ────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    token: str
    user: "UserOut"

class TokenPayload(BaseModel):
    user_id: str
    tenant_id: str
    role: str
    username: str
    fronteira: Optional[str] = None


# ── User ────────────────────────────────────────────────

class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "operador"
    fronteira: Optional[str] = None

class UserUpdate(BaseModel):
    fronteira: Optional[str] = None
    password: Optional[str] = None

class UserOut(BaseModel):
    id: str
    username: str
    role: str
    fronteira: Optional[str] = None

    class Config:
        from_attributes = True


# ── Veiculo ─────────────────────────────────────────────

class VeiculoIn(BaseModel):
    matricula: str
    marca: Optional[str] = None
    carga: Optional[str] = None
    ncont: Optional[str] = None

class VeiculoOut(BaseModel):
    id: str
    matricula: str
    marca: Optional[str] = None
    carga: Optional[str] = None
    ncont: Optional[str] = None

    class Config:
        from_attributes = True


# ── Log Entry ───────────────────────────────────────────

class LogEntryOut(BaseModel):
    id: str
    user: str
    mov: str
    text: str
    zona: Optional[str] = None
    contactavel: Optional[bool] = None
    is_ping: bool = False
    is_edit: bool = False
    edited_by: Optional[str] = None
    edited_at: Optional[datetime] = None
    created_at: datetime
    changes_json: Optional[str] = None

    class Config:
        from_attributes = True

class LogEntryCreate(BaseModel):
    text: str
    mov: Optional[str] = "viagem"
    zona: Optional[str] = None
    contactavel: Optional[bool] = None
    is_ping: bool = False

class LogEntryEdit(BaseModel):
    text: str


# ── Photo ───────────────────────────────────────────────

class PhotoOut(BaseModel):
    id: str
    instance: str
    filename: str
    original_name: Optional[str] = None
    uploaded_by: Optional[str] = None
    created_at: datetime
    url: Optional[str] = None

    class Config:
        from_attributes = True


# ── Viagem ──────────────────────────────────────────────

class ViagemCreate(BaseModel):
    t1: str
    tipo_t1: str = "contentor"
    processo: Optional[str] = None
    bl: Optional[str] = None
    du: Optional[str] = None
    t1_emissao: Optional[datetime] = None
    t1_validade: Optional[datetime] = None
    t1_partida: Optional[datetime] = None
    t1_chegada: Optional[datetime] = None
    motorista: str
    carta: Optional[str] = None
    telefone: Optional[str] = None
    whatsapp: Optional[str] = None
    transportador: Optional[str] = None
    risco: Optional[str] = "1"
    matricula: Optional[str] = None
    marca: Optional[str] = None
    carga: Optional[str] = None
    ncontentor: Optional[str] = None
    cliente: Optional[str] = None
    consignatario: Optional[str] = None
    ref_cliente: Optional[str] = None
    fronteira: str
    funcionario: Optional[str] = None
    fiscal_nome: Optional[str] = None
    fiscal_tel: Optional[str] = None
    saida: Optional[datetime] = None
    limite: Optional[datetime] = None
    obs: Optional[str] = None
    veiculos: Optional[List[VeiculoIn]] = None
    custom_fields_json: Optional[str] = None

class ViagemUpdate(BaseModel):
    motorista: Optional[str] = None
    telefone: Optional[str] = None
    whatsapp: Optional[str] = None
    carta: Optional[str] = None
    matricula: Optional[str] = None
    marca: Optional[str] = None
    carga: Optional[str] = None
    ncontentor: Optional[str] = None
    transportador: Optional[str] = None
    risco: Optional[str] = None
    fronteira: Optional[str] = None
    cliente: Optional[str] = None
    consignatario: Optional[str] = None
    t1: Optional[str] = None
    bl: Optional[str] = None
    du: Optional[str] = None
    processo: Optional[str] = None
    fiscal_nome: Optional[str] = None
    fiscal_tel: Optional[str] = None
    limite: Optional[datetime] = None
    t1_emissao: Optional[datetime] = None
    t1_validade: Optional[datetime] = None
    t1_partida: Optional[datetime] = None
    t1_chegada: Optional[datetime] = None
    funcionario: Optional[str] = None
    aguarda_processamento: Optional[bool] = None
    custom_fields_json: Optional[str] = None
    reason: str  # always required

class ViagemOut(BaseModel):
    id: str
    t1: str
    tipo_t1: str
    processo: Optional[str] = None
    bl: Optional[str] = None
    du: Optional[str] = None
    t1_emissao: Optional[datetime] = None
    t1_validade: Optional[datetime] = None
    t1_partida: Optional[datetime] = None
    t1_chegada: Optional[datetime] = None
    motorista: str
    carta: Optional[str] = None
    telefone: Optional[str] = None
    whatsapp: Optional[str] = None
    transportador: Optional[str] = None
    risco: Optional[str] = None
    matricula: Optional[str] = None
    marca: Optional[str] = None
    carga: Optional[str] = None
    ncontentor: Optional[str] = None
    cliente: Optional[str] = None
    consignatario: Optional[str] = None
    ref_cliente: Optional[str] = None
    fronteira: str
    funcionario: Optional[str] = None
    fiscal_nome: Optional[str] = None
    fiscal_tel: Optional[str] = None
    saida: Optional[datetime] = None
    limite: Optional[datetime] = None
    criado_em: datetime
    last_update: datetime
    movimento: str
    concluido: bool
    aguarda_processamento: bool = False
    luanda_done: bool = False
    luanda_done_by: Optional[str] = None
    luanda_done_at: Optional[datetime] = None
    fronteira_done: bool = False
    fronteira_done_at: Optional[datetime] = None
    t1_stamp: Optional[str] = None
    t1_stamp_date: Optional[str] = None
    t1_stamp_obs: Optional[str] = None
    veiculos: List[VeiculoOut] = []
    logs: List[LogEntryOut] = []
    custom_fields_json: Optional[str] = None

    class Config:
        from_attributes = True

class MovimentoUpdate(BaseModel):
    movimento: str  # viagem | parado


# ── Pedido ──────────────────────────────────────────────

class PedidoLogCreate(BaseModel):
    log_entry_id: str
    proposed_text: str
    reason: str

class PedidoViagemCreate(BaseModel):
    viagem_id: str
    changes_json: str  # JSON array of {field, old, new}
    new_data_json: str  # JSON object with proposed values
    reason: str

class PedidoOut(BaseModel):
    id: str
    viagem_id: str
    type: str
    status: str
    log_entry_id: Optional[str] = None
    original_text: Optional[str] = None
    proposed_text: Optional[str] = None
    changes_json: Optional[str] = None
    new_data_json: Optional[str] = None
    reason: Optional[str] = None
    requested_by: Optional[str] = None
    requested_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    t1: Optional[str] = None
    motorista: Optional[str] = None

    class Config:
        from_attributes = True


# ── Config ──────────────────────────────────────────────

class ConfigUpdate(BaseModel):
    email: Optional[str] = None
    alert_hours: Optional[float] = None
    night_start: Optional[str] = None
    night_end: Optional[str] = None
    t1_alert_warning_days: Optional[int] = None
    t1_alert_critical_days: Optional[int] = None

class ConfigOut(BaseModel):
    email: Optional[str] = None
    alert_hours: float = 3.0
    night_start: str = "21:00"
    night_end: str = "05:00"
    fronteira_contacts_json: Optional[str] = None
    route_baselines_json: Optional[str] = None
    t1_alert_warning_days: int = 3
    t1_alert_critical_days: int = 1

    class Config:
        from_attributes = True

class FronteiraContactsUpdate(BaseModel):
    contacts_json: str  # JSON: {"Luvo": {"nome":"...", "tel":"..."}, ...}

class RouteBaselinesUpdate(BaseModel):
    baselines_json: str  # JSON: {"Luvo": 2, "Noqui": 3, "Luau": 5}


# ── Completion ──────────────────────────────────────────

class DeleteViagemRequest(BaseModel):
    reason: str

class AguardaProcessamentoRequest(BaseModel):
    aguarda: bool
    obs: Optional[str] = None

class ConcluirLuandaRequest(BaseModel):
    pass  # just needs auth

class ConcluirFronteiraRequest(BaseModel):
    numero: str
    data: Optional[str] = None
    obs: Optional[str] = None


# ── Tenant ──────────────────────────────────────────────

class TenantCreate(BaseModel):
    name: str
    slug: str
    admin_username: str = "admin"
    admin_password: str = "admin123"

class TenantOut(BaseModel):
    id: str
    name: str
    slug: str
    active: bool
    created_at: datetime

    class Config:
        from_attributes = True
