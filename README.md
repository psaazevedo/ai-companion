# Personal AI Companion

Initial scaffold for the personal AI companion:

- `backend/` contains the FastAPI app, WebSocket endpoint, agent pipeline, and voice/model wrappers.
- `frontend/` contains the Expo app shell, orb UI, hold-to-talk button, and WebSocket client.

## Current Status

This repo now includes a Phase 1 foundation:

- FastAPI app with `/health` and `/ws/{user_id}`
- Basic agent orchestration with mock fallback mode
- Groq-backed chat, speech-to-text, and text-to-speech behind environment config
- Postgres/pgvector memory architecture for episodic, semantic, procedural, and graph memory
- Versioned semantic/procedural memory with provenance, supersession, and archive reactivation
- Supabase Edge Function scaffold for free-ish `gte-small` embeddings during development
- Background consolidation plus proactive insight scanning in-process during development
- A first contextual state layer that calibrates responses from recent conversation patterns
- A rolling dialogue profile that learns hedging, indirectness, rambling, and disfluency patterns from conversations
- Expo app shell with a minimal orb interface, hold-to-talk flow, and a visual memory atlas on web

## Backend

1. Create a virtual environment.
2. Install dependencies from `backend/pyproject.toml`.
3. Copy `backend/.env.example` to `backend/.env`.
4. Start a Postgres database with the `pgvector` extension available. The repo includes a local `pgvector/pgvector:pg16` Docker Compose service you can mirror in Supabase or local Postgres.
5. Add your `GROQ_API_KEY`.
6. Add `DATABASE_URL` for your Postgres/Supabase database.
7. For free testing embeddings, deploy the Supabase Edge Function in [supabase/functions/embed/index.ts](/Users/pauloazevedo/Documents/AI-Companion/supabase/functions/embed/index.ts).
8. Set `MOCK_MODE=false`.
9. Run:

```bash
cd backend
uvicorn main:app --reload
```

Without a deployed embedding function, the memory architecture still uses Postgres, but retrieval will fall back to lexical ranking until embeddings are configured.

### Background Memory + Proactivity

The backend now includes two in-process background loops for development:

- `memory-consolidation`
- `proactive-scan`

They are controlled with:

```bash
BACKGROUND_RUNNER_ENABLED=true
CONSOLIDATION_INTERVAL_SECONDS=900
PROACTIVE_SCAN_INTERVAL_SECONDS=300
```

The proactive API surface currently includes:

- `GET /proactive/latest/{user_id}`
- `GET /proactive/insights/{user_id}`
- `POST /proactive/scan/{user_id}`
- `POST /proactive/insights/{insight_id}/dismiss`
- `POST /proactive/insights/{insight_id}/delivered`

### Memory API

The memory layer now supports:

- provenance-backed semantic and procedural memories
- fact/procedure versioning with `valid_from`, `valid_to`, and `superseded_by`
- archive reactivation when old memories become contextually relevant again
- state-aware retrieval that biases support/procedural memory under stress
- dialogue adaptation via per-turn speech-pattern signals plus a rolling `dialogue_profiles` model
- retrieval evals for goal, stress, person, change, and archive-recall queries

Useful routes:

- `GET /memory/atlas/{user_id}`
- `GET /memory/search/{user_id}?q=...`
- `GET /memory/evals/{user_id}`
- `GET /memory/dialogue-profile/{user_id}`
- `POST /memory/consolidate/{user_id}`
- `POST /memory/{layer}/{memory_id}/pin`
- `POST /memory/{layer}/{memory_id}/archive`
- `POST /memory/{layer}/{memory_id}/outdated`
- `POST /memory/{layer}/{memory_id}/correct`
- `POST /memory/{layer}/merge`

## Supabase Embeddings

The backend is set up to call a Supabase Edge Function named `embed`:

- [supabase/functions/embed/index.ts](/Users/pauloazevedo/Documents/AI-Companion/supabase/functions/embed/index.ts)
- [supabase/config.toml](/Users/pauloazevedo/Documents/AI-Companion/supabase/config.toml)

Deploy it with the Supabase CLI after logging in and linking your project:

```bash
supabase login
supabase link --project-ref cnouazormdmurtlpknkf
supabase functions deploy embed --no-verify-jwt
```

The function uses Supabase's built-in `gte-small` model, so the backend is configured for `384`-dimensional vectors.

## Frontend

1. Install dependencies from `frontend/package.json`.
2. Copy `frontend/.env.example` to `frontend/.env` if you want to override the default WebSocket URL.
3. Run:

```bash
cd frontend
npm install
npm run start
```

By default the app connects to `ws://127.0.0.1:8000/ws`.

## Next Build Steps

1. Expose memory editing controls in the atlas using the new backend mutation routes.
2. Use the dialogue profile to drive endpointing, pause tolerance, and barge-in behavior in the voice loop.
3. Strengthen proactive timing and judgment so insights surface less often but better.
4. Add external sensory/context inputs like weather, calendar, and voice-baseline state.
