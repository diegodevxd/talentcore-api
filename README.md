# TalentCore API

REST microservice for employee vacation management. Employees check their vacation balance and request days off, direct managers approve or reject requests from their own reports, and HR administrators register employees.

Built with **FastAPI**, **SQLAlchemy** and **SQLite**, and generated as part of the agent-driven SDLC workshop (`taller_agentes_sdlc`).

## Contents of this folder

| Path | Purpose |
|------|---------|
| `app/main.py` | FastAPI application: routes, RBAC checks and balance calculation |
| `app/models.py` | SQLAlchemy models (`Empleado`, `SolicitudVacaciones`), Pydantic schemas and database session |
| `app/__init__.py` | Marks `app` as a Python package |
| `tests/test_api.py` | Pytest suite covering acceptance criteria AC-01, AC-02 and AC-03 |
| `tests/__init__.py` | Marks `tests` as a Python package |
| `probar_api.py` | End-to-end smoke script that calls a running server over HTTP (Spanish output) |
| `requirements.txt` | Python dependencies |
| `Dockerfile` | Container image based on `python:3.11-slim` |
| `docker-compose.yml` | Runs the API container on port `8000` |
| `.github/workflows/ci.yml` | GitHub Actions pipeline: installs dependencies and runs `pytest` on push and pull request to `main` |
| `talentcore.db` | Local SQLite database created at runtime (not versioned) |

## Business rules

**Vacation balance**

- Employees with less than 1 year of seniority get 12 days.
- From 1 year onward: `min(12 + 2 * (anios_antiguedad - 1), 20)` days.
- Available balance = total days − days in `APPROVED` requests.

**Request lifecycle**

`PENDING` → `APPROVED` or `REJECTED` (by the direct manager only). Only `PENDING` requests can be reviewed.

**Roles**

| Role | Permissions |
|------|-------------|
| `EMPLEADO` | Query own balance and submit requests |
| `MANAGER` | Approve or reject requests from direct reports (`manager_id` match) |
| `ADMIN_RRHH` | Create employees (after the first one is created) |

## Endpoints

| Method | Path | Header | Description |
|--------|------|--------|-------------|
| `GET` | `/health` | — | Service health check |
| `POST` | `/api/v1/empleados` | `X-User-Id` | Create an employee. The first record needs no header; afterwards the caller must be `ADMIN_RRHH` |
| `GET` | `/api/v1/vacaciones/saldo/{empleado_id}` | — | Vacation balance for an employee |
| `POST` | `/api/v1/vacaciones/solicitar` | — | Request vacation days (`400` if the balance is insufficient) |
| `POST` | `/api/v1/vacaciones/{solicitud_id}/revisar` | `X-User-Id` | Approve or reject a request (`403` if the caller is not the direct manager) |

Interactive documentation is available at `http://localhost:8000/docs` while the server runs.

> **Note:** authorization is based only on the `X-User-Id` header, as described in the workshop's `ARCHITECTURE.md`. It is not suitable for production as-is. The audit report recommends JWT authentication, Alembic migrations and structured logging.

## Running locally

Requires Python 3.11.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Start the server
uvicorn app.main:app --reload --port 8000

# In another terminal, run the smoke test against the server
python probar_api.py

# Run the test suite
pytest -v
```

> `tests/test_api.py` drops and recreates all tables in `talentcore.db` before each test, so run it against a disposable database if you need to keep local data.

## Running with Docker

```bash
docker compose up --build
```

The API is then available at `http://localhost:8000`.

## Continuous integration

The workflow in `.github/workflows/ci.yml` runs on every push and pull request to `main`:

1. Checks out the repository.
2. Sets up Python 3.11.
3. Installs `requirements.txt`.
4. Runs `pytest -v`.
