# AI Workflow Engine — Minimal Graph Engine (Option A: Code Review Mini-Agent)

## Overview
This repo implements:
- A minimal workflow/graph engine (nodes, state, edges, branching, looping).
- A simple tool registry.
- FastAPI endpoints:
  - `POST /graph/create` — create a graph
  - `POST /graph/run` — run a graph with initial state
  - `GET  /graph/state/{run_id}` — get run state
  - `GET  /graph/ws/{run_id}` — (WebSocket) stream logs for a run

It also includes an **Option A** example workflow (Code Review Mini-Agent)
that extracts functions, checks a naive complexity, and detects basic issues.


## Installation and Steps to run the project
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

1. Clone or download the project

    ai_workflow_engine/
├── requirements.txt
└── app/
    ├── main.py
    ├── graph_engine.py
    ├── example_graphs.py
    └── agents/
        └── code_review_nodes.py

2. Create and activate a virtual environment
    python -m venv venv
venv\Scripts\activate

3. Install dependencies

    pip install -r requirements.txt

4. Start the FastAPI server

    uvicorn app.main:app --reload

5. Confirm the server is running

    http://localhost:8000/

6. Run the workflow

    http://localhost:8000/docs

7. Check the workflow result

    http://localhost:8000/graph/state/<RUN_ID>

8. Stream logs in real time (optional)

    ws://localhost:8000/graph/ws/<RUN_ID>

