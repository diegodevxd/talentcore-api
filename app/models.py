from typing import Optional

from fastapi import Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import (
    CheckConstraint,
    Column,
    create_engine,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import (
    Session,
    backref,
    declarative_base,
    relationship,
    sessionmaker,
)

SQLALCHEMY_DATABASE_URL = "sqlite:///./talentcore.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class Empleado(Base):
    __tablename__ = "empleados"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    rol = Column(String, nullable=False)  # EMPLADO | MANAGER | ADMIN_RRHH
    anios_antiguedad = Column(Integer, nullable=False, default=1)
    manager_id = Column(Integer, ForeignKey("empleados.id"), nullable=True)

    manager = relationship(
        "Empleado",
        remote_side=[id],
        backref=backref("subordinados", cascade="all, delete-orphan"),
    )


class SolicitudVacaciones(Base):
    __tablename__ = "solicitudes_vacaciones"

    id = Column(Integer, primary_key=True, autoincrement=True)
    empleado_id = Column(Integer, ForeignKey("empleados.id"), nullable=False)
    dias_solicitados = Column(Integer, nullable=False)
    motivo = Column(String, nullable=True)
    estado = Column(String, nullable=False, default="PENDING")
    revisado_por_id = Column(Integer, ForeignKey("empleados.id"), nullable=True)

    __table_args__ = (CheckConstraint("dias_solicitados > 0", name="ck_dias_positive"),)

    empleado = relationship("Empleado", foreign_keys=[empleado_id])
    revisado_por = relationship("Empleado", foreign_keys=[revisado_por_id])


class EmpleadoCreate(BaseModel):
    nombre: str
    email: str
    rol: str = Field(..., pattern="^(EMPLEADO|MANAGER|ADMIN_RRHH)$")
    anios_antiguedad: int
    manager_id: Optional[int] = None


class EmpleadoResponse(EmpleadoCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)


class SaldoResponse(BaseModel):
    empleado_id: int
    dias_totales: int
    dias_aprobados: int
    saldo_disponible: int
    model_config = ConfigDict(from_attributes=True)


class SolicitudCreate(BaseModel):
    empleado_id: int
    dias_solicitados: int = Field(..., gt=0)
    motivo: Optional[str] = None


class RevisionRequest(BaseModel):
    accion: str = Field(..., pattern="^(APPROVE|REJECT)$")


class SolicitudResponse(BaseModel):
    id: int
    empleado_id: int
    dias_solicitados: int
    motivo: Optional[str] = None
    estado: str
    revisado_por_id: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)
