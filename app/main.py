from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import Dict, Any
from uuid import UUID
import logging

# Import engine helpers
from .graph_engine import create_graph, get_run, run_graph_async

# Import example workflow
from .example_graphs import create_example_graph

# Import agents so node/functions register on startup
from .agents import code_review_nodes  # noqa: F401

app = FastAPI(title="Minimal Graph Engine - Code Review Mini Agent")

logger = logging.getLogger("uvicorn.error")

# Will hold the Option A example graph ID
EXAMPLE_GRAPH_ID = None


# -------------------- MODELS --------------------

class GraphCreateRequest(BaseModel):
    entry: str
    nodes: Dict[str, Dict]  # node_key → {"fn":..., "next":..., "meta":...}

class GraphCreateResponse(BaseModel):
    graph_id: UUID

class GraphRunRequest(BaseModel):
    graph_id: UUID
    initial_state: Dict[str, Any] = {}

class GraphRunResponse(BaseModel):
    run_id: UUID


# -------------------- STARTUP EVENT --------------------

@app.on_event("startup")
async def startup_event():
    """
    Automatically create the Option A (Code Review Mini-Agent) workflow graph.
    """
    global EXAMPLE_GRAPH_ID
    EXAMPLE_GRAPH_ID = create_example_graph()
    logger.info(f"[Startup] Example Graph (Option A) created: {EXAMPLE_GRAPH_ID}")


# -------------------- BASIC ROOT ENDPOINT --------------------

@app.get("/")
async def root():
    return {
        "message": "AI Workflow Engine is running!",
        "example_graph_id": str(EXAMPLE_GRAPH_ID)
    }


# -------------------- API: CREATE GRAPH --------------------

@app.post("/graph/create", response_model=GraphCreateResponse)
async def api_graph_create(req: GraphCreateRequest):
    """
    Create a graph dynamically using JSON input.
    """
    gid = create_graph(req.dict())
    return {"graph_id": gid}


# -------------------- API: RUN GRAPH --------------------

@app.post("/graph/run", response_model=GraphRunResponse)
async def api_graph_run(req: GraphRunRequest):
    """
    Start a graph execution with initial state.
    """
    try:
        run_id = run_graph_async(req.graph_id, req.initial_state or {})
    except KeyError:
        raise HTTPException(status_code=404, detail="Graph not found")

    return {"run_id": run_id}


# -------------------- API: GET STATE OF A RUN --------------------

@app.get("/graph/state/{run_id}")
async def api_graph_state(run_id: UUID):
    """
    Fetch latest state, logs, and current node of a running or finished workflow.
    """
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    return {
        "run_id": run.run_id,
        "graph_id": run.graph_id,
        "current_node": run.current_node,
        "state": run.state,
        "status": run.status,
        "logs": run.logs,
    }


# -------------------- WEBSOCKET LOG STREAMING --------------------

@app.websocket("/graph/ws/{run_id}")
async def websocket_logs(websocket: WebSocket, run_id: UUID):
    """
    Stream logs for a specific workflow run in real-time.
    """
    await websocket.accept()
    run = get_run(run_id)
    if not run:
        await websocket.send_json({"error": "Run not found"})
        await websocket.close()
        return

    q = run.log_queue

    try:
        while True:
            msg = await q.get()

            # Sentinel value: None means end of run
            if msg is None:
                await websocket.send_json({"event": "done"})
                break

            await websocket.send_json({"log": msg})

    except WebSocketDisconnect:
        return
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
