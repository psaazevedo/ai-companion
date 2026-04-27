# Personal AI Companion

A voice-first AI companion designed to become more useful the longer it knows you.

This is not meant to be a disposable chatbot or a session-based assistant. The product direction is a continuous relationship: one companion, one memory, across voice and text, with a visual memory atlas that lets you inspect how the system understands you over time.

The north star is simple on the surface and deep underneath:

- Speak naturally.
- Write when text is better.
- Let the system remember, consolidate, adapt, and surface useful context later.
- Make memory transparent enough that the user can trust, correct, and shape it.

## Product Vision

Most AI tools are reactive and stateless. They wait for a prompt, answer from a thin slice of context, and then forget most of what made the interaction meaningful.

This project is exploring the opposite pattern:

- **Continuous relationship:** every interaction belongs to the same long-running thread.
- **Layered memory:** the system separates events, beliefs, habits, procedures, and relationships instead of treating memory as one flat blob.
- **Voice-first presence:** the primary interface is an orb and a microphone, with text available as a deeper mode.
- **Proactive intelligence:** the companion should eventually notice patterns and surface high-value insights without being asked.
- **User-visible cognition:** the Memory Atlas shows what the system believes, where it came from, and how ideas connect.
- **Adaptive conversation:** the companion should learn how the user speaks, including rambling, pauses, indirectness, stutters, and preferred response style.

The goal is a companion that feels less like a tool you operate and more like a trusted mind that grows alongside you.

## What Exists Today

This repo contains a working early product foundation:

- A web-first Expo interface with an animated particle orb, voice mode, chat mode, and memory atlas.
- A FastAPI backend with WebSocket conversation flow.
- Groq-backed chat, speech-to-text, and text-to-speech behind environment configuration.
- A real Postgres/Supabase memory architecture using relational tables plus pgvector.
- Episodic, semantic, procedural, and graph memory layers.
- Memory provenance, versioning, archive/reactivation mechanics, and consolidation jobs.
- Dialogue profiling that begins to learn speech and communication patterns.
- A proactive insight pipeline for surfacing useful observations.
- A visual atlas for exploring memory nodes and relationships.

This is still an early build, but the core shape is already oriented around the final architecture rather than a throwaway prototype.

## Core Capabilities

### Voice And Text As One Thread

Voice and text are not separate products. They both feed the same remembered relationship.

Voice mode is designed for presence: fast, minimal, ambient, and centered around the orb. Chat mode opens a deeper written thread for longer reflection, history, and precise input.

The system stores both modes into the same memory pipeline so spoken conversations and written messages reinforce the same understanding of the user.

### Memory Atlas

The Memory Atlas is the first transparency surface for the companion's mind.

It is not intended to be a normal settings table. It is a visual map of concepts, preferences, procedures, goals, and relationships. The goal is to help the user understand:

- what the companion currently believes,
- where that belief came from,
- how strongly it is reinforced,
- what related memories are nearby,
- what is active, archived, pinned, outdated, or superseded.

This matters because a system with powerful memory has to be inspectable. If it remembers forever, the user needs a way to see and correct what it thinks it knows.

### Proactive Insights

The proactive layer is meant to surface only when there is something genuinely worth saying.

The long-term bar is high: not reminders, not generic advice, not "you seem stressed" filler. A good proactive insight should feel like the companion connected dots across time and noticed something useful at the right moment.

Current development includes the first insight queue, scan loop, delivery state, and dismissal flow. The judgment layer still needs to become much stricter as the product matures.

## The Memory System

Memory is the core product moat. The companion should become dramatically more useful on day 365 than day 1 because it has accumulated context, corrected itself, and learned the user's patterns.

The system is intentionally layered.

### 1. Episodic Memory

Episodic memory stores what happened.

Each conversation turn can become an episode with:

- timestamp,
- user input,
- companion response,
- summary,
- emotional tone,
- entities mentioned,
- salience score,
- recall count,
- stability,
- provenance metadata,
- vector embedding.

This answers questions like:

- "What did I say about this last week?"
- "When did I first mention this project?"
- "What changed between then and now?"

Episodic memory is closest to lived experience. It preserves context before abstraction.

### 2. Semantic Memory

Semantic memory stores what appears to be true.

Repeated or important episodes are consolidated into beliefs, preferences, goals, and facts, such as:

- "The user prefers direct answers when stressed."
- "The user is building an AI companion."
- "The user wants memory to be layered and inspectable."

Semantic memories include confidence, reinforcement count, source episodes, validity windows, and supersession links. This prevents the system from treating every extracted fact as equally certain or permanent.

This layer answers:

- "What do you know about me?"
- "What are my current goals?"
- "What preferences have I reinforced over time?"

### 3. Procedural Memory

Procedural memory stores how to help.

This is the companion's learned playbook for the user. It captures strategies that work, such as:

- "When the user is frustrated with UI, make the next change directly and keep the explanation short."
- "When the user is exploring architecture, explain tradeoffs before implementation."
- "When the user is stressed, ground first, then offer one concrete next step."

Procedural memory is what makes the companion feel personally adaptive rather than merely knowledgeable.

This layer answers:

- "How should I respond to this person?"
- "What has worked before?"
- "What communication style helps in this state?"

### 4. Graph Memory

Graph memory stores what is connected.

People, projects, places, tools, goals, preferences, habits, and recurring problems become nodes. Relationships become weighted edges. Reinforced edges strengthen over time; stale edges weaken but do not need to vanish.

This supports non-obvious reasoning:

- a project connected to a stress pattern,
- a person connected to a goal,
- a preference connected to a failure mode,
- a recurring problem connected to a procedure that helped before.

This layer answers:

- "What is this related to?"
- "Why does this keep coming up?"
- "Which old memory is suddenly relevant again?"

### 5. Dialogue Profile

The dialogue profile is a memory layer for speech and conversational rhythm.

The companion should learn whether the user tends to:

- ramble before finding the point,
- pause mid-thought,
- hedge or speak indirectly,
- repeat phrases,
- prefer concise or reflective answers,
- need more time before endpointing,
- interrupt naturally during speech.

This matters for making voice feel human. Normal conversation has overlap, hesitation, correction, interruption, and unfinished thoughts. The system should adapt to the user's speech patterns instead of treating every pause as the end of a turn.

### 6. Archive And Reactivation

The system is designed to archive, not forget.

Old or low-salience memories can move out of active retrieval so they do not pollute current context. But archived memories remain recoverable and can reactivate when new context makes them relevant again.

This gives the system a human-like attention model:

- active memories shape the present,
- archived memories stay quietly available,
- pinned memories remain permanently important,
- outdated memories can be superseded without being erased.

## Memory Lifecycle

The intended flow is:

1. A conversation creates an episode.
2. The episode is embedded and scored for salience.
3. Entities and relationships update the graph.
4. Retrieval uses vector search, graph context, memory status, confidence, and user state.
5. Nightly consolidation promotes repeated patterns into semantic or procedural memory.
6. Contradictions create new versions instead of silently overwriting old beliefs.
7. Archived memories can reactivate when the present makes them useful again.

This is the beginning of a "sleep cycle" for the companion: each day should leave the system more organized than it was before.

## Architecture

```text
Interface Layer
  Expo app, animated orb, voice mode, chat mode, memory atlas

Realtime Layer
  WebSocket conversation stream

Agent Layer
  assess input -> retrieve context -> reason -> validate -> respond -> store

Memory Layer
  episodic + semantic + procedural + graph + dialogue profile

Data Layer
  Supabase/Postgres + pgvector + object storage

Background Layer
  consolidation, archive/reactivation, proactive insight scanning
```

## Tech Stack

### Frontend

- Expo / React Native / TypeScript
- Web-first development surface
- Animated particle orb rendered on web
- Voice mode and chat mode
- Memory Atlas visualization

### Backend

- FastAPI
- WebSockets
- Groq for LLM/STT/TTS when configured
- In-process background loops for development
- Postgres/Supabase for durable memory
- pgvector for semantic retrieval

### Memory Infrastructure

- Supabase Postgres
- pgvector embeddings
- Supabase Edge Function scaffold for `gte-small` embeddings during development
- Relational provenance and versioning
- Graph nodes and weighted edges persisted in Postgres

## Repository Structure

```text
backend/
  api/              HTTP and WebSocket routes
  core/             agent orchestration, model wrappers, voice
  memory/           episodic, semantic, procedural, graph, retrieval, consolidation
  proactive/        insight generation and delivery judgment
  sensory/          contextual state and signal integration
  db/               database clients and migrations

frontend/
  app/              Expo app entry
  components/       orb, chat, mode toggle, memory atlas, notifications
  hooks/            voice, WebSocket, conversation feed, proactive insight
  stores/           local agent state

supabase/
  functions/embed/  embedding Edge Function scaffold
```

## Running The Backend

1. Create and activate a Python virtual environment.
2. Install dependencies from `backend/pyproject.toml`.
3. Copy `backend/.env.example` to `backend/.env`.
4. Add `GROQ_API_KEY` if you want real model, STT, and TTS calls.
5. Add `DATABASE_URL` for Supabase/Postgres.
6. Set `MOCK_MODE=false` when real providers are configured.
7. Run:

```bash
cd backend
uvicorn main:app --reload
```

Without embeddings configured, the backend can still store memory and use lexical ranking. With embeddings configured, retrieval uses pgvector similarity.

## Running The Frontend

1. Install dependencies.
2. Copy `frontend/.env.example` to `frontend/.env` if you need to override the WebSocket URL.
3. Run:

```bash
cd frontend
npm install
npm run start
```

By default the app connects to:

```text
ws://127.0.0.1:8000/ws
```

## Supabase Embeddings

The backend can call a Supabase Edge Function named `embed`:

- [supabase/functions/embed/index.ts](/Users/pauloazevedo/Documents/AI-Companion/supabase/functions/embed/index.ts)
- [supabase/config.toml](/Users/pauloazevedo/Documents/AI-Companion/supabase/config.toml)

Deploy it with:

```bash
supabase login
supabase link --project-ref <project-ref>
supabase functions deploy embed --no-verify-jwt
```

The current development setup uses Supabase's built-in `gte-small` model and `384`-dimensional vectors.

## Useful Backend Routes

### Memory

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

### Proactive

- `GET /proactive/latest/{user_id}`
- `GET /proactive/insights/{user_id}`
- `POST /proactive/scan/{user_id}`
- `POST /proactive/insights/{insight_id}/dismiss`
- `POST /proactive/insights/{insight_id}/delivered`

### Internet Tools

- `GET /tools/internet/search?q=...`

The backend supports a controlled internet layer for current information. The model does not receive raw browser access or API keys. Instead, the backend decides when a turn needs live external context, calls a configured provider, and injects a compact source-backed result block into the prompt.

Supported providers:

- `INTERNET_SEARCH_PROVIDER=tavily` with `TAVILY_API_KEY`
- `INTERNET_SEARCH_PROVIDER=brave` with `BRAVE_SEARCH_API_KEY`

If no key is configured, internet search fails closed and the model is instructed to say live web access is unavailable rather than inventing current facts.

## Development Background Jobs

The backend includes in-process background loops for local development:

```bash
BACKGROUND_RUNNER_ENABLED=true
CONSOLIDATION_INTERVAL_SECONDS=900
PROACTIVE_SCAN_INTERVAL_SECONDS=300
```

Current loops:

- `memory-consolidation`
- `proactive-scan`

Production should eventually move these to a more durable queue/scheduler.

## Near-Term Product Priorities

1. Improve consolidation so similar memories reinforce existing abstractions instead of creating duplicate nodes.
2. Make proactive insights rarer, more contextual, and more valuable.
3. Use dialogue profile data to improve endpointing, interruption handling, and pause tolerance.
4. Add memory editing directly inside the Atlas: pin, correct, merge, archive, and mark outdated.
5. Add sensory context carefully: weather, calendar, voice tone baseline, and later health signals with explicit consent.
6. Improve retrieval evals so memory quality can be tested instead of judged only by feel.

## Product Principles

- **Remember, but stay inspectable.** Powerful memory must be transparent and correctable.
- **Archive, do not erase by default.** The system manages attention, not existence.
- **Be proactive only when it is worth it.** Silence is better than weak insight.
- **Adapt to the person.** The companion should learn how the user thinks and speaks.
- **Stay honest about uncertainty.** Confidence should be calibrated, not performed.
- **Keep the interface simple.** The intelligence should feel deep without making the user manage complexity.
