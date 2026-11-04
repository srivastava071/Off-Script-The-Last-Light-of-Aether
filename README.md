# Off Script: The Last Light of Aether

A story-driven adventure game in which autonomous LLM-driven characters pursue a narrative goal
and adapt when the player interferes. Capstone project (SIH PS SIH26195, Student Innovation).

> Status: **Step 9 of 10** — playable frontend: menu, character select, live island map, actions, dialogue, endings.

## Layout

```
backend/        FastAPI simulation server (Python 3.11+)
  app/
    api/        HTTP routes (health, runs)
    core/       configuration
    schemas/    API request and response models
    services/   run manager (locks, real-time driver, auth, rate limits)
    persistence/ SQLite tables and repository
    models/     typed world state (Pydantic)
    engine/     deterministic simulation: island data, movement, objects, obstacles,
                rules (action validation), timeline (clock), knowledge, simulation tick, run, invariants
    agents/     character agents (belief view, fallback planner, observe-decide-act loop) and the Director
  tests/        pytest suite
frontend/       React + TypeScript + Vite client
  src/
    game/       Phaser island scene and map geometry
    components/ panels: actions, dialogue, team, objectives, event log
    pages/      main menu, character select, game, ending
    hooks/      useRun: polls the backend for state and events
    services/   typed API client
docs/           architecture, game design, API, demo scenarios (added later)
.env.example    configuration template
```

## Backend setup (Windows, Git Bash or PowerShell)

```bash
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt   # macOS/Linux: .venv/bin/python
.venv/Scripts/python -m pytest
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000
```

Then open http://localhost:8000/api/health or the interactive docs at http://localhost:8000/docs.

Runs are stored in `backend/data/offscript.db` (created automatically).

## Frontend setup

Needs Node.js 20+ (tested with 24 LTS). Start the backend first (port 8000), then:

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173 (proxies /api to the backend)
npm test           # unit and component tests
npm run build      # type-check + production build into frontend/dist
```

The frontend only displays what the backend reports and sends player requests; the backend owns the
clock, the rules and every character decision. Refreshing the page resumes the same run (the deadline
keeps running on the server).

### Controls

- **Main menu:** *Watch Default Mode* (the story runs by itself) or *Start Game Mode* (pick a character).
- **Radio command bar (Game Mode):** type — or press the microphone and speak — instructions such as
  *"Kabir, pick up the timber and fix the bridge. Meera, scout the forest and mark the traps."* or
  *"I'll go to the temple and pull the lever."* The server turns them into validated orders (with the LLM
  when available, otherwise a keyword parser). Teammates obey every order they are able to carry out, walk
  to the right place by themselves, and say why when they can't; your own instructions run as an autopilot
  until you act by hand. Orders replace earlier ones; "carry on" sends a teammate back to their own plan.
  The speaker button reads replies aloud. Voice input uses the browser's speech recognition (Chrome/Edge),
  which sends the audio to the browser vendor's speech service.
- **Action panel:** every action the rules allow right now, with its duration; greyed actions show why
  they are unavailable. Each action takes island time, during which you cannot act again.
- **Talk panel:** speak with teammates at your location. Replies are marked *template* or *AI · model*.
- **Team panel / map:** click a character to highlight them; autonomous characters show their current
  goal and plan.
- **Event log:** filter by Story, Adaptation (plan changes caused by new information, and AI choices)
  or Dialogue.
- Default Mode adds **Pause** and **Skip 30s**; Game Mode cannot be paused.

## API in brief

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Status, and whether AI is in `mock` or `live` mode |
| POST | `/api/runs` | Create a run: `{"mode": "default"}` or `{"mode": "game", "player_character": "aria"}`. Returns `run_id` and a one-time `token` |
| GET | `/api/runs` | Recent runs (`?status=finished` for completed ones) |
| GET | `/api/runs/{id}/state` | Full state for the UI, including the player's available actions |
| POST | `/api/runs/{id}/start` | Start the run; the backend clock then runs on its own |
| POST | `/api/runs/{id}/actions` | Player action, e.g. `{"type": "move", "destination": "bridge", "request_id": "..."}` |
| POST | `/api/runs/{id}/dialogue` | Talk to a character: `{"target_id": "kabir", "message": "..."}` |
| GET | `/api/runs/{id}/events?after=SEQ` | Event log since a sequence number |
| GET | `/api/runs/{id}/characters` | Character status, plans, trust |
| POST | `/api/runs/{id}/advance` | Fast-forward 1–120 ticks (time only moves forward) |
| POST | `/api/runs/{id}/pause` | Pause/resume — Default Mode only |
| POST | `/api/runs/{id}/restart` | Start over as a new run (the old one is abandoned) |

Every run-specific call needs the header `X-Run-Token: <token>`. Rule rejections return `200` with
`"ok": false` and an explanation; HTTP errors mean a protocol problem (401, 404, 409, 422, 429).

`requirements.lock` records the exact versions last verified.

## Configuration

Copy `.env.example` to `.env` in the repository root and fill in your keys there. **Never put keys in
`.env.example`** — it is a shared template; `.env` is git-ignored.

### Mock mode (default, no key)

With `AI_PROVIDER=mock` (or no `.env`), everything runs offline: the rule-based planner makes every
decision and replies come from templates. `/api/health` reports `ai_mode: "mock"`, and every reply in
the event log carries `generated_by: "template"`, so mock output is never presented as LLM output.

### Live LLM mode (free tiers)

Set `AI_PROVIDER=openai_compatible` and add one or more keys:

| Provider | Key variable | Default model |
|---|---|---|
| Groq | `GROQ_API_KEY` | `qwen/qwen3.8-27b` |
| Google Gemini | `GEMINI_API_KEY` | `gemini-flash-lite-latest` |
| OpenRouter | `OPENROUTER_API_KEY` | `openrouter/free` (picks any currently free model) |

Providers are tried in `LLM_PROVIDER_ORDER`; when one is rate-limited, overloaded or failing, the next
is used. Free-tier model names change often — override them with `GROQ_MODEL`, `GEMINI_MODEL`,
`OPENROUTER_MODEL`. Keys stay on the backend and never reach the browser or the logs.

What the LLM does — and does not do:

- **Strategy (Game Mode only):** when something significant happens to an autonomous character, the
  LLM is asked, in the background, to choose between the valid strategies the rule-based planner
  offers. It can pick one; it cannot invent actions. Nothing waits for it, and a stale or invalid
  answer is discarded (the log says so).
- **Dialogue:** characters answer the player in character, grounded only in what they know.
- **Epilogue:** a short narration of the ending, built from the recorded key events.
- **Default Mode** stays deterministic; the LLM only writes the epilogue.
- Limits: `LLM_TIMEOUT_SECONDS`, `LLM_MAX_RETRIES`, `LLM_MAX_CALLS_PER_MINUTE` (shared budget),
  `LLM_MAX_DELIBERATIONS_PER_RUN`. Usage per run is reported in `story.ai` of the state.
