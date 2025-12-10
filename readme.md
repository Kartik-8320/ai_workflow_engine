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

## Install
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
