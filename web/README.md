# Lingua Ledger web

1. `cd web && npm install`
2. `cp .env.example .env.local` and set `NEXT_PUBLIC_API_URL` to the FastAPI backend (default http://localhost:8000).
3. Start the backend from the repo root: `uv run uvicorn api.main:app --reload`.
4. `npm run dev` and open http://localhost:3000 (Workbench, Evidence, About).
5. `npm run build` checks types and lint; on Vercel set the project root to `web/` and add `NEXT_PUBLIC_API_URL`.
