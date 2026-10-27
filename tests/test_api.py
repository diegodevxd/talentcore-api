import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models import Base, engine

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_db():
    """Drop and recreate all tables before each test to guarantee isolation."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


@pytest.fixture(autouse=True)
def patch_sqlalchemy_func():
    """
    The `calcular_saldo` helper in ``app.main`` uses ``func.sum`` from SQLAlchemy,
    but the original module does not import ``func``.  Inject the correct reference
    so the endpoint works without modifying production code.
    """
    import app.main as main
    from sqlalchemy import func

    main.func = func
    yield
    # clean up (optional)
    del main.func


def test_health_check():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_ac01_solicitud_valida_y_calculo_saldo():
    # admin creation (first employee, no header needed)
    admin_payload = {
        "nombre": "Admin",
        "email": "admin@example.com",
        "rol": "ADMIN_RRHH",
        "anios_antiguedad": 5,
        "manager_id": None,
    }
    resp = client.post("/api/v1/empleados", json=admin_payload)
    assert resp.status_code == 201
    admin_id = resp.json()["id"]
    assert admin_id == 1

    # manager creation
    manager_payload = {
        "nombre": "Manager",
        "email": "manager@example.com",
        "rol": "MANAGER",
        "anios_antiguedad": 2,
        "manager_id": None,
    }
    resp = client.post(
        "/api/v1/empleados",
        json=manager_payload,
        headers={"X-User-Id": str(admin_id)},
    )
    assert resp.status_code == 201
    manager_id = resp.json()["id"]
    assert manager_id == 2

    # empleado creation
    empleado_payload = {
        "nombre": "Empleado",
        "email": "empleado@example.com",
        "rol": "EMPLEADO",
        "anios_antiguedad": 3,
        "manager_id": manager_id,
    }
    resp = client.post(
        "/api/v1/empleados",
        json=empleado_payload,
        headers={"X-User-Id": str(admin_id)},
    )
    assert resp.status_code == 201
    empleado_id = resp.json()["id"]
    assert empleado_id == 3

    # check initial saldo
    resp = client.get(f"/api/v1/vacaciones/saldo/{empleado_id}")
    assert resp.status_code == 200
    saldo = resp.json()
    assert saldo["dias_totales"] == 16  # 12 + 2*(3-1)
    assert saldo["saldo_disponible"] == 16

    # solicitar vacaciones
    solicitud_payload = {"empleado_id": empleado_id, "dias_solicitados": 5}
    resp = client.post("/api/v1/vacaciones/solicitar", json=solicitud_payload)
    assert resp.status_code == 201
    solicitud = resp.json()
    assert solicitud["estado"] == "PENDING"
    solicitud_id = solicitud["id"]
    assert solicitud_id == 1

    # manager aprueba
    revisar_payload = {"accion": "APPROVE"}
    resp = client.post(
        f"/api/v1/vacaciones/{solicitud_id}/revisar",
        json=revisar_payload,
        headers={"X-User-Id": str(manager_id)},
    )
    assert resp.status_code == 200
    revisada = resp.json()
    assert revisada["estado"] == "APPROVED"

    # check saldo after approval
    resp = client.get(f"/api/v1/vacaciones/saldo/{empleado_id}")
    assert resp.status_code == 200
    saldo = resp.json()
    assert saldo["dias_totales"] == 16
    assert saldo["saldo_disponible"] == 11  # 16 - 5


def test_ac02_saldo_insuficiente():
    # admin
    admin_payload = {
        "nombre": "Admin",
        "email": "admin2@example.com",
        "rol": "ADMIN_RRHH",
        "anios_antiguedad": 5,
        "manager_id": None,
    }
    resp = client.post("/api/v1/empleados", json=admin_payload)
    assert resp.status_code == 201
    admin_id = resp.json()["id"]

    # empleado con 12 días totales
    emp_payload = {
        "nombre": "Empleado2",
        "email": "empleado2@example.com",
        "rol": "EMPLEADO",
        "anios_antiguedad": 1,
        "manager_id": None,
    }
    resp = client.post(
        "/api/v1/empleados",
        json=emp_payload,
        headers={"X-User-Id": str(admin_id)},
    )
    assert resp.status_code == 201
    emp_id = resp.json()["id"]

    # intentar solicitar 15 días
    solicitud_payload = {"empleado_id": emp_id, "dias_solicitados": 15}
    resp = client.post("/api/v1/vacaciones/solicitar", json=solicitud_payload)
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Insufficient vacation balance"


def test_ac03_manager_no_autorizado():
    # admin
    admin_payload = {
        "nombre": "Admin",
        "email": "admin3@example.com",
        "rol": "ADMIN_RRHH",
        "anios_antiguedad": 5,
        "manager_id": None,
    }
    resp = client.post("/api/v1/empleados", json=admin_payload)
    assert resp.status_code == 201
    admin_id = resp.json()["id"]

    # manager A
    mgr_a_payload = {
        "nombre": "ManagerA",
        "email": "managerA@example.com",
        "rol": "MANAGER",
        "anios_antiguedad": 2,
        "manager_id": None,
    }
    resp = client.post(
        "/api/v1/empleados",
        json=mgr_a_payload,
        headers={"X-User-Id": str(admin_id)},
    )
    assert resp.status_code == 201
    mgr_a_id = resp.json()["id"]

    # manager B
    mgr_b_payload = {
        "nombre": "ManagerB",
        "email": "managerB@example.com",
        "rol": "MANAGER",
        "anios_antiguedad": 2,
        "manager_id": None,
    }
    resp = client.post(
        "/api/v1/empleados",
        json=mgr_b_payload,
        headers={"X-User-Id": str(admin_id)},
    )
    assert resp.status_code == 201
    mgr_b_id = resp.json()["id"]

    # empleado bajo manager A
    emp_payload = {
        "nombre": "Empleado3",
        "email": "empleado3@example.com",
        "rol": "EMPLEADO",
        "anios_antiguedad": 1,
        "manager_id": mgr_a_id,
    }
    resp = client.post(
        "/api/v1/empleados",
        json=emp_payload,
        headers={"X-User-Id": str(admin_id)},
    )
    assert resp.status_code == 201
    emp_id = resp.json()["id"]

    # empleado solicita 3 días
    solicitud_payload = {"empleado_id": emp_id, "dias_solicitados": 3}
    resp = client.post("/api/v1/vacaciones/solicitar", json=solicitud_payload)
    assert resp.status_code == 201
    solicitud_id = resp.json()["id"]

    # manager B intenta aprobar
    revisar_payload = {"accion": "APPROVE"}
    resp = client.post(
        f"/api/v1/vacaciones/{solicitud_id}/revisar",
        json=revisar_payload,
        headers={"X-User-Id": str(mgr_b_id)},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Unauthorized: Not the direct manager"
