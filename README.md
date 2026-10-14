# ACME Employee Salary Management

Starter repository for the ACME Employee Salary Management project.

## Planned stack

- **Backend:** FastAPI (Python)
- **Frontend:** React with JavaScript
- **Database:** SQLite

## Repository layout

```text
backend/   FastAPI backend
frontend/  React frontend
docs/      Project documentation and requirements
```

See [`docs/ACME_Employee_Salary_Management_Requirements.pdf`](docs/ACME_Employee_Salary_Management_Requirements.pdf) for the project requirements.

## Backend setup

The backend uses Python 3.10 or newer, FastAPI, Uvicorn, and Python's built-in SQLite support.

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API is available at `http://127.0.0.1:8000`, with interactive API documentation at `/docs`. Check `http://127.0.0.1:8000/health` to verify the API and SQLite connection. The default database is created at `backend/data/acme_salary_management.db`. Set `DATABASE_PATH` to use another SQLite file; relative paths resolve from `backend/`, and absolute paths are also supported.

To install pytest and run the backend tests from `backend/`, use `python -m pip install -r requirements-dev.txt` followed by `python -m pytest`.

## Database

SQLite is used for local development. The employees table is initialized when the backend starts. PostgreSQL is the planned deployment database.
