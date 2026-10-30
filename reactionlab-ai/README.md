# ReactionLab AI

Upload a photo of a chemistry lab-notebook page and get back a structured reaction record.

## How it works

Image -> React -> FastAPI -> Gemini Vision -> JSON -> React

The model only transcribes what is written on the page; missing information is returned as "Not provided".

## Prerequisites

- Python 3.11+
- Node 20+
- A Gemini API key from https://aistudio.google.com/apikey

## Backend setup (Windows)

```powershell
cd backend
```

```powershell
python -m venv .venv
```

```powershell
.venv\Scripts\python -m pip install -r requirements.txt
```

```powershell
copy .env.example .env
```

Edit `backend/.env` and set `GEMINI_API_KEY`. Then start the server:

```powershell
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Config: `GEMINI_MODEL` sets the primary model; `GEMINI_FALLBACK_MODEL` (default `gemini-3.5-flash`, empty disables) is tried once if the primary is overloaded (503/429).

## Frontend setup

```powershell
cd frontend
```

```powershell
npm install
```

```powershell
npm run dev
```

Open http://localhost:5173 (Vite proxies `/api` to the backend on port 8000).

## Running tests

```powershell
cd backend
```

```powershell
.venv\Scripts\python -m pip install -r requirements-dev.txt
```

```powershell
.venv\Scripts\python -m pytest -q
```

## Endpoints

`POST /api/extract` reads a notebook image; `POST /api/predict` takes `{"reactants": "...", "conditions": "..."}` and returns an AI-predicted reaction (every field marked `source: ai`). Unsafe requests are declined with 422.

## API contract

See [CONTRACT.md](CONTRACT.md) for the exact request, response and error shapes.

## Plugging in another vision model

1. Implement `ReactionExtractor` (`backend/app/extractors/base.py`) in a new module under `backend/app/extractors/`.
2. Register it in `get_extractor` in `backend/app/extractors/__init__.py`.
3. Select it with the `EXTRACTOR` environment variable (default `gemini`).
