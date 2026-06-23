# Ripple

Ripple is a code dependency analysis platform that parses Python repositories, constructs dependency graphs, and identifies critical files, architectural bottlenecks, and change impact paths.

## Features (Planned)

* Parse Python repositories using AST
* Build file-level dependency graphs
* Detect dependency cycles
* Compute criticality scores (PageRank, centrality)
* Impact analysis for proposed changes
* Interactive graph visualization
* REST API for repository analysis

## Tech Stack

### Backend

* Python 3.11
* FastAPI
* PostgreSQL
* SQLAlchemy
* NetworkX

### Frontend

* React
* Vite
* Cytoscape.js

### Infrastructure

* Docker
* Docker Compose

---

## Project Structure

```text
ripple/
├── backend/
├── frontend/
├── docs/
└── docker-compose.yml
```

---

## Prerequisites

* Docker
* Docker Compose
* Python 3.11+ (optional for local backend development)
* Node.js 20+ (optional for local frontend development)

---

## Running with Docker

From the project root:

```bash
docker compose up --build
```

Backend:

```text
http://localhost:8000
```

Frontend:

```text
http://localhost:5173
```

---

## Backend Development

```bash
cd backend

python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

Run:

```bash
uvicorn app.main:app --reload
```

---

## Frontend Development

```bash
cd frontend

npm install
npm run dev
```

---

## Current Status

### Phase 0 – Infrastructure

* [x] Docker setup
* [x] PostgreSQL container
* [x] Backend container
* [x] Frontend container