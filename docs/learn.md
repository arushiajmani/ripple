# Ripple — Learning Log

> Running notes on mistakes, fixes, and concepts to internalize while building this project.
> Each update is logged with date and time below.

---

## Update Log

| Date & time | Summary |
|-------------|---------|
| 2026-06-23 15:19 IST | Initial log: Docker setup mistakes, Compose CLI, permissions, networking, PEP 668, Phase 0 concepts |
| 2026-06-23 15:21 IST | Python venv + `backend/requirements.txt` created; initial deps installed |

---

## Mistakes & Gotchas

### Docker: `docker compose` vs `docker-compose`
- **What happened:** `docker compose up` failed with `'compose' is not a docker command`.
- **Fix:** On this Debian setup, use `docker-compose` (hyphen). The Compose V2 plugin (`docker compose`) is not installed; `docker-compose-plugin` wasn't available via apt either.
- **Takeaway:** Check which Compose CLI you have before copying commands from docs.

### Docker: permission denied on `/var/run/docker.sock`
- **What happened:** After `sudo usermod -aG docker $USER`, `docker ps` still returned permission denied.
- **Fix:** Group changes don't apply to already-open terminals. Use `newgrp docker` in each terminal, log out/in for a permanent fix, or use `sudo` temporarily.
- **Takeaway:** `usermod` updates your account — not your current shell session.

### Docker: second terminal still denied
- **What happened:** Terminal 1 worked after `newgrp docker`; terminal 2 still got permission denied.
- **Fix:** Run `newgrp docker` in every new terminal, or log out/in once.
- **Takeaway:** Each terminal has its own group membership until you start a fresh login session.

### Docker networking: `localhost` inside a container
- **Concept:** From the backend container, Postgres is at hostname `db` (the Compose service name), not `localhost`.
- **Why:** `localhost` inside a container refers to that container itself, not other services.
- **Takeaway:** Use service names from `docker-compose.yml` in connection strings — e.g. `postgresql://ripple:ripple@db:5432/ripple`.

### Docker: `depends_on` ≠ database ready
- **Concept:** `depends_on` only controls **start order**, not whether Postgres has finished initializing.
- **Risk:** Backend can crash on startup if it connects before Postgres accepts connections.
- **Takeaway:** Add retry/wait logic in the backend, or use a healthcheck + `depends_on: condition: service_healthy`.

### Python: PEP 668 externally-managed-environment
- **What happened:** `pip install ...` on the host failed with `externally-managed-environment`.
- **Fix:** Use a virtual environment (`python3 -m venv .venv`) or install dependencies inside the Docker image — don't pip install globally on Debian.
- **Takeaway:** Host Python is for tooling; app dependencies live in venv or container.

### Python: virtual environment location
- **Setup:** `python3 -m venv backend/.venv` then `backend/.venv/bin/pip install -r backend/requirements.txt`
- **Activate:** `source backend/.venv/bin/activate`
- **Takeaway:** Venv lives next to `requirements.txt` in `backend/` — keeps host Python clean (avoids PEP 668 errors).

### Initial `requirements.txt` packages (what each is for)
| Package | Purpose |
|---------|---------|
| `fastapi` + `uvicorn` | HTTP API and ASGI server |
| `sqlalchemy` + `psycopg2-binary` | PostgreSQL ORM and driver |
| `alembic` | Database migrations |
| `networkx` | Graph algorithms (PageRank, cycles, etc.) |
| `python-dotenv` | Load env vars from `.env` |
| `python-multipart` | Zip file uploads on `POST /analyze` |
| `pytest` + `httpx` | Tests and async HTTP test client |

### Wrong packages installed via pip
- **What happened:** Attempted to install unrelated packages (`praw`, `transformers`, `torch`, etc.).
- **Ripple stack:** See table above — stick to `backend/requirements.txt`.
- **Takeaway:** Don't cargo-cult dependencies from other projects.

---

## Concepts to Be Clear On

### Modular monolith
- One Python process, separated by module folders (`parser/`, `graph/`, `api/`, etc.).
- Not microservices — no network boundaries between components.
- **Interview line:** "Clean module boundaries so components could become services later, without paying distributed complexity upfront."

### Docker Compose networking
- Compose creates an internal network; services reach each other by **service name**.
- Ports like `5432:5432` expose services to the **host**; inside the network, use `db:5432`.
- Three services: `frontend` → `backend` → `db`.

### Async job pattern
- Analysis takes 30–120 seconds — can't hold an HTTP request open.
- `POST /analyze` returns `repo_id` immediately; client polls `GET /status/{id}` until `complete`.
- Used by video encoding, ML training, report generation — same pattern everywhere.

### Compute vs storage separation
- **NetworkX** runs graph algorithms (PageRank, betweenness, cycle detection) in memory.
- **PostgreSQL** persists repositories, files, dependencies, scores, cycles.
- **Interview line:** "Neo4j would be a second graph system for the same data. Postgres persists; NetworkX computes."

### Why PostgreSQL, not Neo4j
- Data model is relational (repos → files → dependencies → scores).
- Graph traversal queries aren't the bottleneck — algorithm execution is.
- Neo4j adds ops complexity without replacing NetworkX.

### `DATABASE_URL` format
```
postgresql://USER:PASSWORD@HOST:PORT/DATABASE
postgresql://ripple:ripple@db:5432/ripple
```
- `HOST` = Compose service name when running in Docker.
- `HOST` = `localhost` when connecting from the host machine (with port published).

### Phase 0 vs Phase 1
- **Phase 0:** Infrastructure — Docker, Postgres reachable, FastAPI `/health`, React loads.
- **Phase 1:** Analysis engine — AST parser, graph builder, algorithms (the core).
- Validate the foundation before building features on top of it.

---

## Commands That Work (this machine)

```bash
# Python venv (local dev, no Docker)
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Start Postgres only
docker-compose up db

# Verify Postgres (may need newgrp docker or sudo in fresh terminals)
docker-compose exec db psql -U ripple -d ripple -c "SELECT 1;"
sudo docker-compose exec db psql -U ripple -d ripple -c "SELECT 1;"

# Stop everything
docker-compose down

# Refresh docker group in current terminal
newgrp docker
```

---

## Verified So Far

- [x] Docker installed and daemon running
- [x] `docker-compose` installed (standalone, not plugin)
- [x] Postgres container starts (`database system is ready to accept connections`)
- [x] `SELECT 1` succeeds against `ripple` database
- [x] Python venv at `backend/.venv` with initial dependencies installed
- [ ] Backend container can reach Postgres (needs `backend/` scaffold)
- [ ] Full `docker-compose up` with all three services

---

*Last updated: 2026-06-23 15:21 IST — Phase 0, Python venv + requirements.txt*
