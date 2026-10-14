# Local setup

## Prerequisites

- Python 3.10 or newer.
- Node.js 18, or 20 or newer (required by the locked Vite version).
- npm, installed with Node.js.

## Backend

Run these commands from the repository root unless a different folder is shown.

Create and activate a virtual environment from `backend/`:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Install the development dependencies, also from `backend/`, when running tests:

```bash
python -m pip install -r requirements-dev.txt
```

The default SQLite database is `backend/data/acme_salary_management.db`. Optionally set `DATABASE_PATH` to another SQLite database path. Relative paths are resolved from `backend/`; absolute paths are also accepted. For example, from `backend/`:

```bash
export DATABASE_PATH=data/local.db
```

The default allowed frontend origin is `http://localhost:5173`. To change it, set `CORS_ORIGINS` to a comma-separated list of origins, including scheme and port, from `backend/`:

```bash
export CORS_ORIGINS=http://localhost:5173
```

Seed the database from `backend/`:

```bash
python -m scripts.seed
```

This adds 10,000 deterministic employees. It can be run again safely: existing employee IDs are skipped, so rerunning does not duplicate them. The script reports how many records it added and the total.

Start the API from `backend/`:

```bash
uvicorn app.main:app --reload
```

The API is at `http://localhost:8000`; interactive documentation is at `http://localhost:8000/docs`. The health check is `http://localhost:8000/health`.

Run backend tests from `backend/` with the virtual environment active and development requirements installed:

```bash
python -m pytest
```

## Frontend

In a second terminal, install and start the frontend from `frontend/`:

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

`.env.example` sets `VITE_API_URL=http://localhost:8000`. Edit `frontend/.env` if the API uses a different URL, and restart the dev server after changing it. The frontend is at `http://localhost:5173`.

Build the frontend from `frontend/` with:

```bash
npm run build
```

## How to verify it works

Open `http://localhost:5173`. The dashboard should show 10,000 employees and 8 currencies. Open the Employees directory; it should show 20 employees per page.

## Troubleshooting

- **`No module named 'app'` from uvicorn or pytest:** run the command from `backend/` with the virtual environment active. The module path `app.main:app` and backend pytest configuration expect that working directory.
- **CORS errors:** the frontend origin must match an entry in `CORS_ORIGINS`, including its port. If the frontend runs on a port other than 5173, set `CORS_ORIGINS` to that frontend origin and restart the API.

SQLite is used for local development for now. PostgreSQL is the planned deployment target.
