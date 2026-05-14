"""
Control — Database Models
All tables scoped by tenant_id for multi-tenant isolation.
"""

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, Text, DateTime, ForeignKey,
    create_engine, Index
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from datetime import datetime, timezone
import uuid
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./control_dev.db")

# Railway PostgreSQL uses postgres:// but SQLAlchemy needs postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def gen_id():
    return uuid.uuid4().hex[:12]


def utcnow():
    return datetime.now(timezone.utc)


# ── Tenant ──────────────────────────────────────────────

class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(String(12), primary_key=True, default=gen_id)
    name = Column(String(200), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    active = Column(Boolean, default=True)

    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    viagens = relationship("Viagem", back_populates="tenant", cascade="all, delete-orphan")
    pedidos = relationship("Pedido", back_populates="tenant", cascade="all, delete-orphan")
    config = relationship("Config", back_populates="tenant", uselist=False, cascade="all, delete-orphan")


# ── User ────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(String(12), primary_key=True, default=gen_id)
    tenant_id = Column(String(12), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    username = Column(String(100), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="operador")  # admin, operador, fronteira
    fronteira = Column(String(100), nullable=True)  # only for role=fronteira
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    tenant = relationship("Tenant", back_populates="users")

    __table_args__ = (
        Index("ix_users_tenant_username", "tenant_id", "username", unique=True),
    )


# ── Viagem ──────────────────────────────────────────────

class Viagem(Base):
    __tablename__ = "viagens"

    id = Column(String(12), primary_key=True, default=gen_id)
    tenant_id = Column(String(12), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)

    # T1 / document
    t1 = Column(String(100), nullable=False)
    tipo_t1 = Column(String(20), default="contentor")  # contentor | geral
    processo = Column(String(100))
    bl = Column(String(100))
    du = Column(String(100))
    t1_emissao = Column(DateTime(timezone=True))    # T1 issue date
    t1_validade = Column(DateTime(timezone=True))   # T1 expiry deadline
    t1_partida = Column(DateTime(timezone=True))    # When T1 left terminal
    t1_chegada = Column(DateTime(timezone=True))    # When truck arrived at border

    # Driver
    motorista = Column(String(200), nullable=False)
    carta = Column(String(100))
    telefone = Column(String(50))
    whatsapp = Column(String(50))
    transportador = Column(String(200))
    risco = Column(String(5), default="1")

    # Vehicle (single — contentor mode)
    matricula = Column(String(50))
    marca = Column(String(100))
    carga = Column(String(200))
    ncontentor = Column(String(50))

    # Route
    cliente = Column(String(200))
    consignatario = Column(String(200))
    ref_cliente = Column(String(100))
    fronteira = Column(String(100), nullable=False)
    funcionario = Column(String(200))

    # Fiscal
    fiscal_nome = Column(String(200))
    fiscal_tel = Column(String(50))

    # Custom fields (JSON blob — for Local Control and tenant-specific fields)
    custom_fields_json = Column(Text)

    # Dates
    saida = Column(DateTime(timezone=True))
    limite = Column(DateTime(timezone=True))
    criado_em = Column(DateTime(timezone=True), default=utcnow)
    last_update = Column(DateTime(timezone=True), default=utcnow)

    # Status
    movimento = Column(String(20), default="viagem")  # viagem | parado | aguarda
    concluido = Column(Boolean, default=False)
    aguarda_processamento = Column(Boolean, default=False)  # arrived but pending processing

    # Completion — Luanda side
    luanda_done = Column(Boolean, default=False)
    luanda_done_by = Column(String(100))
    luanda_done_at = Column(DateTime(timezone=True))

    # Completion — Frontier side
    fronteira_done = Column(Boolean, default=False)
    fronteira_done_at = Column(DateTime(timezone=True))
    t1_stamp = Column(String(100))
    t1_stamp_date = Column(String(20))
    t1_stamp_obs = Column(Text)

    tenant = relationship("Tenant", back_populates="viagens")
    logs = relationship("LogEntry", back_populates="viagem", cascade="all, delete-orphan", order_by="LogEntry.created_at")
    veiculos = relationship("Veiculo", back_populates="viagem", cascade="all, delete-orphan")
    photos = relationship("Photo", back_populates="viagem", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_viagens_tenant", "tenant_id"),
        Index("ix_viagens_tenant_concluido", "tenant_id", "concluido"),
        Index("ix_viagens_tenant_fronteira", "tenant_id", "fronteira"),
    )


# ── Veiculo (multi-vehicle for tipo_t1=geral) ──────────

class Veiculo(Base):
    __tablename__ = "veiculos"

    id = Column(String(12), primary_key=True, default=gen_id)
    viagem_id = Column(String(12), ForeignKey("viagens.id", ondelete="CASCADE"), nullable=False)
    matricula = Column(String(50), nullable=False)
    marca = Column(String(100))
    carga = Column(String(200))
    ncont = Column(String(50))

    viagem = relationship("Viagem", back_populates="veiculos")


# ── Log Entry ───────────────────────────────────────────

class LogEntry(Base):
    __tablename__ = "log_entries"

    id = Column(String(12), primary_key=True, default=gen_id)
    viagem_id = Column(String(12), ForeignKey("viagens.id", ondelete="CASCADE"), nullable=False)
    user = Column(String(100), nullable=False)
    mov = Column(String(20), default="viagem")
    text = Column(Text, nullable=False)
    zona = Column(String(300))
    contactavel = Column(Boolean, nullable=True)
    is_ping = Column(Boolean, default=False)
    is_edit = Column(Boolean, default=False)
    edited_by = Column(String(100))
    edited_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=utcnow)

    # JSON-encoded changes for edit logs
    changes_json = Column(Text)

    viagem = relationship("Viagem", back_populates="logs")

    __table_args__ = (
        Index("ix_logs_viagem", "viagem_id"),
    )


# ── Photo ───────────────────────────────────────────────

class Photo(Base):
    __tablename__ = "photos"

    id = Column(String(12), primary_key=True, default=gen_id)
    viagem_id = Column(String(12), ForeignKey("viagens.id", ondelete="CASCADE"), nullable=False)
    instance = Column(String(20), nullable=False)  # saida, viagem, chegada, stamp
    filename = Column(String(255), nullable=False)
    original_name = Column(String(255))
    uploaded_by = Column(String(100))
    created_at = Column(DateTime(timezone=True), default=utcnow)

    viagem = relationship("Viagem", back_populates="photos")

    __table_args__ = (
        Index("ix_photos_viagem_instance", "viagem_id", "instance"),
    )


# ── Pedido (edit request) ───────────────────────────────

class Pedido(Base):
    __tablename__ = "pedidos"

    id = Column(String(12), primary_key=True, default=gen_id)
    tenant_id = Column(String(12), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    viagem_id = Column(String(12), ForeignKey("viagens.id", ondelete="CASCADE"), nullable=False)
    type = Column(String(30), default="log-edit")  # log-edit | viagem-edit
    status = Column(String(20), default="pendente")  # pendente | aprovado | rejeitado

    # For log edits
    log_entry_id = Column(String(12))
    original_text = Column(Text)
    proposed_text = Column(Text)

    # For viagem edits
    changes_json = Column(Text)  # JSON array of {field, old, new}
    new_data_json = Column(Text)  # JSON of proposed field values

    reason = Column(Text)
    requested_by = Column(String(100))
    requested_at = Column(DateTime(timezone=True), default=utcnow)
    resolved_by = Column(String(100))
    resolved_at = Column(DateTime(timezone=True))

    # Metadata for display
    t1 = Column(String(100))
    motorista = Column(String(200))

    tenant = relationship("Tenant", back_populates="pedidos")

    __table_args__ = (
        Index("ix_pedidos_tenant_status", "tenant_id", "status"),
    )


# ── Config (per tenant) ────────────────────────────────

class Config(Base):
    __tablename__ = "configs"

    id = Column(String(12), primary_key=True, default=gen_id)
    tenant_id = Column(String(12), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True)
    email = Column(String(200))
    alert_hours = Column(Float, default=3.0)
    night_start = Column(String(10), default="21:00")
    night_end = Column(String(10), default="05:00")

    # JSON-encoded fronteira contacts: {"Luvo": {"nome":"...", "tel":"..."}, ...}
    fronteira_contacts_json = Column(Text)

    # JSON-encoded route baselines: {"Luvo": 2, "Noqui": 3, "Luau": 5} (days)
    route_baselines_json = Column(Text)

    # T1 alert thresholds (days)
    t1_alert_warning_days = Column(Integer, default=3)    # yellow alert
    t1_alert_critical_days = Column(Integer, default=1)   # red alert

    tenant = relationship("Tenant", back_populates="config")


# ── Create tables ───────────────────────────────────────

def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
