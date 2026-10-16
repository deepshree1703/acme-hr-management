# ACME Employee Salary Management

Starter repository for the ACME Employee Salary Management project.

## Links

- **Demo video:** [Watch the demo](https://drive.google.com/file/d/1dg4X7WrxJLlAXs0Nvxr4e0W8Ot7n6UT8/view?usp=sharing)
- **Live application:** [Open the live application](https://acme-hr-management-one.vercel.app/)
- **Requirements (1 page):** [docs/ACME_Employee_Salary_Management_Requirements.pdf](docs/ACME_Employee_Salary_Management_Requirements.pdf)

## Planned stack

- **Backend:** FastAPI (Python)
- **Frontend:** React with JavaScript
- **Database:** SQLite locally; Supabase PostgreSQL for deployment

## Repository layout

```text
backend/   FastAPI backend
frontend/  React frontend
docs/      Project documentation and requirements
```

See [`docs/ACME_Employee_Salary_Management_Requirements.pdf`](docs/ACME_Employee_Salary_Management_Requirements.pdf) for the project requirements.

## Backend setup

The backend uses Python 3.10 or newer, FastAPI, Uvicorn, Psycopg 3, and Python's built-in SQLite support.

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

`requirements-dev.txt` includes the runtime dependencies from `requirements.txt` (including `psycopg[binary]`) plus pytest and the HTTP test client. For a runtime-only local install, use `python -m pip install -r requirements.txt` instead.

The API is available at `http://127.0.0.1:8000`, with interactive API documentation at `/docs`. Check `http://127.0.0.1:8000/health` to verify the configured database connection. The default local database is created at `backend/data/acme_salary_management.db`. Set `DATABASE_PATH` to use another SQLite file; relative paths resolve from `backend/`, and absolute paths are also supported.

When `DATABASE_URL` is set, the backend uses PostgreSQL through Psycopg 3 instead of SQLite. For Vercel, set it to the Supabase PostgreSQL connection string in server-side environment variables. Without `DATABASE_URL`, local development continues to use `DATABASE_PATH` and SQLite.

To seed 10,000 deterministic fictional employees into the configured database, run from `backend/`:

```bash
python -m scripts.seed
```

From `backend/` with the virtual environment active, run the backend tests with `python -m pytest`.

## Frontend setup

The frontend uses React, JavaScript with JSX, and Vite. Start the backend first, then run the frontend in another terminal:

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Open the local URL printed by Vite (normally `http://localhost:5173`). The API URL defaults to `http://localhost:8000`; set `VITE_API_URL` in `frontend/.env` to point to another backend. Restart Vite after changing environment variables. The dashboard shows headcount and average salary by currency; averages remain in their own currencies and are not combined.

The frontend uses `frontend/public/favicon.svg` as its browser tab icon.

## Database

SQLite is used for local development when `DATABASE_URL` is unset. Supabase PostgreSQL is used for deployment when `DATABASE_URL` is configured. The employees table is initialized when the backend starts.

### PostgreSQL integration test

The PostgreSQL integration test is skipped unless `TEST_DATABASE_URL` points to a dedicated, empty test database. It also requires an explicit write confirmation, refuses to run on Vercel, refuses a target matching `DATABASE_URL`, and refuses a database that already contains employee rows. It removes the rows it seeds but leaves the initialized table and indexes in place. Never point it at production.

From the repository root, set the URL for a disposable PostgreSQL database and run:

```bash
export TEST_DATABASE_URL='postgresql://user:password@host:5432/test_database'
export CONFIRM_TEST_DATABASE_WRITES=YES
backend/.venv/bin/python -m pytest -q backend/tests/test_postgres_integration.py
```

Do not set `TEST_DATABASE_URL` or `CONFIRM_TEST_DATABASE_WRITES` in Vercel. Vercel uses the server-side `DATABASE_URL` setting for the application database.
