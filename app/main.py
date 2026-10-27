from fastapi import FastAPI, Depends, Header, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.models import (
    Base,
    engine,
    get_db,
    Empleado,
    SolicitudVacaciones,
    EmpleadoCreate,
    EmpleadoResponse,
    SaldoResponse,
    SolicitudCreate,
    SolicitudResponse,
    RevisionRequest,
)

app = FastAPI(title="TalentCore API")
Base.metadata.create_all(bind=engine)


def calcular_saldo(emp: Empleado, db: Session) -> tuple[int, int, int]:
    dias_totales = 12 if emp.anios_antiguedad < 1 else min(12 + 2 * (emp.anios_antiguedad - 1), 20)
    dias_aprobados = (
        db.query(SolicitudVacaciones)
        .filter(SolicitudVacaciones.empleado_id == emp.id, SolicitudVacaciones.estado == "APPROVED")
        .with_entities(func.sum(SolicitudVacaciones.dias_solicitados))
        .scalar()
        or 0
    )
    saldo_disponible = dias_totales - dias_aprobados
    return dias_totales, dias_aprobados, saldo_disponible


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post(
    "/api/v1/empleados",
    response_model=EmpleadoResponse,
    status_code=status.HTTP_201_CREATED,
)
def crear_empleado(
    payload: EmpleadoCreate,
    x_user_id: int | None = Header(None, alias="X-User-Id"),
    db: Session = Depends(get_db),
):
    if db.query(Empleado).count() > 0:
        if x_user_id is None:
            raise HTTPException(status_code=403, detail="Missing X-User-Id")
        admin = db.query(Empleado).filter(Empleado.id == x_user_id).first()
        if not admin:
            raise HTTPException(status_code=404, detail="Admin not found")
        if admin.rol != "ADMIN_RRHH":
            raise HTTPException(status_code=403, detail="Only ADMIN_RRHH can create employees")
    nuevo = Empleado(**payload.dict())
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo


@app.get(
    "/api/v1/vacaciones/saldo/{empleado_id}",
    response_model=SaldoResponse,
)
def obtener_saldo(empleado_id: int, db: Session = Depends(get_db)):
    emp = db.query(Empleado).filter(Empleado.id == empleado_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Empleado not found")
    dias_totales, dias_aprobados, saldo = calcular_saldo(emp, db)
    return SaldoResponse(
        empleado_id=emp.id,
        dias_totales=dias_totales,
        dias_aprobados=dias_aprobados,
        saldo_disponible=saldo,
    )


@app.post(
    "/api/v1/vacaciones/solicitar",
    response_model=SolicitudResponse,
    status_code=status.HTTP_201_CREATED,
)
def solicitar_vacaciones(
    payload: SolicitudCreate,
    db: Session = Depends(get_db),
):
    emp = db.query(Empleado).filter(Empleado.id == payload.empleado_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Empleado not found")
    _, _, saldo = calcular_saldo(emp, db)
    if payload.dias_solicitados > saldo:
        raise HTTPException(status_code=400, detail="Insufficient vacation balance")
    solicitud = SolicitudVacaciones(
        empleado_id=payload.empleado_id,
        dias_solicitados=payload.dias_solicitados,
        motivo=payload.motivo,
        estado="PENDING",
    )
    db.add(solicitud)
    db.commit()
    db.refresh(solicitud)
    return solicitud


@app.post(
    "/api/v1/vacaciones/{solicitud_id}/revisar",
    response_model=SolicitudResponse,
    status_code=status.HTTP_200_OK,
)
def revisar_solicitud(
    solicitud_id: int,
    payload: RevisionRequest,
    x_user_id: int = Header(..., alias="X-User-Id"),
    db: Session = Depends(get_db),
):
    solicitud = db.query(SolicitudVacaciones).filter(SolicitudVacaciones.id == solicitud_id).first()
    if not solicitud:
        raise HTTPException(status_code=404, detail="Solicitud not found")
    manager = db.query(Empleado).filter(Empleado.id == x_user_id).first()
    if not manager:
        raise HTTPException(status_code=404, detail="Manager not found")
    empleado = db.query(Empleado).filter(Empleado.id == solicitud.empleado_id).first()
    if manager.rol != "MANAGER" or empleado.manager_id != x_user_id:
        raise HTTPException(status_code=403, detail="Unauthorized: Not the direct manager")
    if solicitud.estado != "PENDING":
        raise HTTPException(status_code=400, detail="Request already processed")
    if payload.accion == "APPROVE":
        solicitud.estado = "APPROVED"
    elif payload.accion == "REJECT":
        solicitud.estado = "REJECTED"
    else:
        raise HTTPException(status_code=400, detail="Invalid action")
    solicitud.revisado_por_id = x_user_id
    db.commit()
    db.refresh(solicitud)
    return solicitud
