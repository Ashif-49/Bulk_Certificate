# Project rules
- Stack: Python 3.11+, FastAPI, SQLAlchemy 2.x, SQLite (Postgres-compatible), Pydantic v2, ReportLab, pytest.
- Keep it simple and explainable: no Celery/Redis, no unnecessary abstractions.
- Layering: routers (HTTP only) -> services (business logic) -> repositories/models (DB). No business logic in routers.
- Every function that does non-obvious work gets a short docstring explaining WHY.
- All new behavior needs a pytest test. Run `pytest` before declaring a task complete.
- Never swallow exceptions silently: record them in the DB (error column) and log them.
- Prefer small, readable files. Add type hints everywhere.
- Update README.md whenever endpoints, setup, or design decisions change.
