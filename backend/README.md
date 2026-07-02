# District360 — Flask Backend

## Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your PostgreSQL credentials
flask db upgrade
flask run
```

## Running Tests

```bash
pytest
```

## Project Structure

See `/docs/ARCHITECTURE.md` for the high-level design. This backend implements the Phase 1 core platform: identity, tenant (district), department, audit, and activity log modules.

District ID:
a09d2217-a2f1-4d1b-b61f-e162d1573d1c

Email:
admin@district360.com

Password:
Admin123