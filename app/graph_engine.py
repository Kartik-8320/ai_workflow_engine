import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, Callable, Optional, List, Union
from uuid import uuid4, UUID
import inspect
import traceback

# ---------------- TOOL REGISTRY ----------------
tools: Dict[str, Callable[..., Any]] = {}

def register_tool(name: str):
    """Decorator to register a tool by name."""
    def decorator(fn: Callable[..., Any]):
        tools[name] = fn
        return fn
    return decorator

# small example tool (useful for Option A)
@register_tool("simple_issue_counter")
def simple_issue_counter(state: Dict[str, Any]) -> Dict[str, Any]:
    cnt = 0
    if "basic_issues" in state:
        cnt += len(state.get("basic_issues", []))
    if state.get("has_high_complexity"):
        cnt += 1
    state["issue_count"] = cnt
    return {"issue_count": cnt}

# ---------------- NODE REGISTRY ----------------
NODE_FUNCS: Dict[str, Callable[[Dict[str, Any]], Any]] = {}

def register_node(name: str):
    """Decorator to register node functions."""
    def decorator(fn: Callable[[Dict[str, Any]], Any]):
        NODE_FUNCS[name] = fn
        return fn
    return decorator

# ---------------- DATA STRUCTURES ----------------
@dataclass
class NodeDef:
    key: str
    fn_name: Optional[str] = None  # name of node function or "tool:<toolname>"
    next: Optional[Union[str, Dict[str, str]]] = None
    meta: Dict[str, Any] = field(default_factory=dict)

@dataclass
class GraphDef:
    graph_id: UUID
    nodes: Dict[str, NodeDef]
    entry: str = ""

@dataclass
class RunState:
    run_id: UUID
    graph_id: UUID
    current_node: Optional[str]
    state: Dict[str, Any]
    status: str = "PENDING"
    logs: List[str] = field(default_factory=list)
    log_queue: asyncio.Queue = field(default_factory=asyncio.Queue)

# ---------------- IN-MEMORY STORES ----------------
GRAPHS: Dict[UUID, GraphDef] = {}
RUNS: Dict[UUID, RunState] = {}

# ---------------- INTERNAL HELPERS ----------------
async def _call_fn(fn: Callable, state: Dict[str, Any]):
    """Call node/tool function (sync or async)."""
    if inspect.iscoroutinefunction(fn):
        return await fn(state)
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: fn(state))

async def _emit(run_state: RunState, msg: str):
    """Append to logs and push to log_queue."""
    run_state.logs.append(msg)
    try:
        await run_state.log_queue.put(msg)
    except Exception:
        pass

def _shortrepr(obj: Any) -> str:
    try:
        s = str(obj)
        return s if len(s) <= 400 else s[:400] + "..."
    except Exception:
        return repr(obj)

# ---------------- ENGINE ----------------
async def execute_graph_run(graph: GraphDef, run_state: RunState):
    run_state.status = "RUNNING"
    await _emit(run_state, f"Run started for graph {graph.graph_id}, entry={graph.entry}")
    try:
        node_key = graph.entry
        visited = 0
        MAX_STEPS = 1000
        while node_key is not None and visited < MAX_STEPS:
            visited += 1
            run_state.current_node = node_key
            node_def = graph.nodes.get(node_key)
            if not node_def:
                await _emit(run_state, f"Node '{node_key}' not found. Stopping.")
                break

            await _emit(run_state, f"Entering node: {node_key}")

            result = None

            # Execute tool or node function
            if node_def.fn_name:
                # tool:toolname -> call tool
                if isinstance(node_def.fn_name, str) and node_def.fn_name.startswith("tool:"):
                    tname = node_def.fn_name.split(":", 1)[1]
                    tool = tools.get(tname)
                    if tool is None:
                        raise RuntimeError(f"Tool '{tname}' not found")
                    res = await _call_fn(tool, run_state.state)
                    result = res
                    if isinstance(res, dict):
                        # merge returned dict into state (non-destructive merge)
                        run_state.state.update(res)
                else:
                    fn = NODE_FUNCS.get(node_def.fn_name)
                    if fn is None:
                        raise RuntimeError(f"Node function '{node_def.fn_name}' not registered")
                    res = await _call_fn(fn, run_state.state)
                    result = res
                    # if node returns dict and does not specify "next", merge into state
                    if isinstance(res, dict) and "next" not in res:
                        run_state.state.update(res)
            else:
                await _emit(run_state, f"Node '{node_key}' has no fn_name; skipping execution.")

            await _emit(run_state, f"Node '{node_key}' completed. result={_shortrepr(result)}")

            # Decide next node
            next_node = None

            # Priority 1: explicit 'next' returned by node
            if isinstance(result, dict) and "next" in result:
                next_node = result["next"]
                await _emit(run_state, f"Node returned explicit next: {next_node}")

            # Priority 2: node_def.next (string or branching dict)
            elif node_def.next:
                if isinstance(node_def.next, str):
                    next_node = node_def.next
                elif isinstance(node_def.next, dict):
                    # branching - evaluate meta.condition if present
                    if "condition" in node_def.meta:
                        cond_expr = node_def.meta.get("condition")
                        try:
                            cond_val = eval(cond_expr, {"state": run_state.state})
                        except Exception as e:
                            raise RuntimeError(f"Error evaluating condition '{cond_expr}': {e}")
                        branch = "true" if cond_val else "false"
                        next_node = node_def.next.get(branch)
                    else:
                        branch_flag = run_state.state.get("last_condition", None)
                        if branch_flag is True or str(branch_flag).lower() == "true":
                            next_node = node_def.next.get("true")
                        else:
                            next_node = node_def.next.get("false")

            # Priority 3: stop request in state
            if run_state.state.get("stop") is True:
                await _emit(run_state, "State requested stop -> finishing run.")
                next_node = None

            node_key = next_node
            await asyncio.sleep(0)  # cooperative yield

        if visited >= MAX_STEPS:
            await _emit(run_state, f"Max steps {MAX_STEPS} reached, aborting.")
            run_state.status = "FAILED"
        else:
            run_state.status = "DONE"
            await _emit(run_state, f"Run finished. status={run_state.status}")

    except Exception as exc:
        tb = traceback.format_exc()
        await _emit(run_state, f"Execution failed: {exc}\n{tb}")
        run_state.status = "FAILED"
    finally:
        # signal completion to websocket consumers
        try:
            await run_state.log_queue.put(None)
        except Exception:
            pass

# ---------------- API HELPERS ----------------
def create_graph(definition: Dict[str, Any]) -> UUID:
    """
    Create a graph from a dict:
    {
      "entry": "start",
      "nodes": {
         "start": {"fn": "extract_functions", "next": "check_complexity"},
         ...
      }
    }
    """
    gid = uuid4()
    nodes: Dict[str, NodeDef] = {}
    for key, info in definition.get("nodes", {}).items():
        fn_name = info.get("fn")
        next_ = info.get("next")
        meta = info.get("meta", {}) or {}
        nodes[key] = NodeDef(key=key, fn_name=fn_name, next=next_, meta=meta)
    graph = GraphDef(graph_id=gid, nodes=nodes, entry=definition.get("entry", ""))
    GRAPHS[gid] = graph
    return gid

def get_graph(gid: UUID) -> Optional[GraphDef]:
    return GRAPHS.get(gid)

def run_graph_async(gid: UUID, initial_state: Dict[str, Any]) -> UUID:
    graph = GRAPHS.get(gid)
    if graph is None:
        raise KeyError("Graph not found")
    run_id = uuid4()
    rs = RunState(run_id=run_id, graph_id=gid, current_node=None, state=initial_state.copy())
    RUNS[run_id] = rs
    asyncio.create_task(execute_graph_run(graph, rs))
    return run_id

def get_run(run_id: UUID) -> Optional[RunState]:
    return RUNS.get(run_id)
