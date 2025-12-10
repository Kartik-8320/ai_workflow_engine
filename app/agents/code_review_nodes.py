from typing import Dict, Any, List
import re
from ..graph_engine import register_node, register_tool

# Register a local tool (optional)
@register_tool("detect_smells")
def detect_smells_tool(state: Dict[str, Any]) -> Dict[str, Any]:
    code = state.get("code", "") or ""
    issues = 0
    lines = code.splitlines()
    for ln in lines:
        if len(ln) > 100:
            issues += 1
        if "TODO" in ln or "FIXME" in ln:
            issues += 1
    out = {"issues": issues, "lines": len(lines)}
    state.update(out)
    return out

# --- Helper: naive function extractor ---
def _extract_functions_from_code(code: str) -> List[Dict[str, Any]]:
    lines = code.splitlines()
    funcs = []
    pattern = re.compile(r'^\s*def\s+(\w+)\s*\(')
    current = None
    current_indent = None
    for i, ln in enumerate(lines):
        m = pattern.match(ln)
        if m:
            if current:
                current["end_line"] = i
                funcs.append(current)
            name = m.group(1)
            indent = len(ln) - len(ln.lstrip(" "))
            current = {"name": name, "start_line": i + 1, "end_line": None, "lines": []}
            current_indent = indent
        elif current:
            if ln.strip() == "":
                current["lines"].append(ln)
            else:
                indent = len(ln) - len(ln.lstrip(" "))
                if indent > current_indent:
                    current["lines"].append(ln)
                else:
                    current["end_line"] = i
                    funcs.append(current)
                    current = None
                    current_indent = None
    if current:
        current["end_line"] = len(lines)
        funcs.append(current)
    return funcs

# Node 1: Extract functions
@register_node("extract_functions")
def extract_functions_node(state: Dict[str, Any]):
    code = state.get("code", "") or ""
    funcs = _extract_functions_from_code(code)
    functions_meta = []
    for f in funcs:
        start = f.get("start_line", 1)
        end = f.get("end_line", start)
        length = (end - start + 1) if end and start else len(f.get("lines", []))
        functions_meta.append({"name": f["name"], "start": start, "end": end, "length": length})
    state["functions"] = functions_meta
    state["functions_count"] = len(functions_meta)
    # continue to complexity check
    return {"next": "check_complexity"}

# Node 2: Check complexity (naive heuristics)
@register_node("check_complexity")
def check_complexity_node(state: Dict[str, Any]):
    code = state.get("code", "") or ""
    functions = state.get("functions", [])
    branching_keywords = [" if ", " for ", " while ", " and ", " or ", "elif ", "case ", "except ", "return "]
    func_scores = []
    lines = code.splitlines()
    for f in functions:
        start = max(f.get("start", 1) - 1, 0)
        end = min(f.get("end", len(lines)), len(lines))
        snippet = "\n".join(lines[start:end])
        score = 0
        for kw in branching_keywords:
            score += snippet.count(kw)
        func_scores.append({"name": f["name"], "complexity_score": score, "length": f.get("length", 0)})
    max_score = max((s["complexity_score"] for s in func_scores), default=0)
    state["complexity"] = {"per_function": func_scores, "max_score": max_score}
    threshold = state.get("complexity_threshold", 5)
    state["has_high_complexity"] = any(s["complexity_score"] > threshold for s in func_scores)
    state["last_condition"] = state["has_high_complexity"]
    return None  # follow graph's next/branching logic

# Node 3: Detect basic issues
@register_node("detect_basic_issues")
def detect_basic_issues_node(state: Dict[str, Any]):
    code = state.get("code", "") or ""
    issues = []
    lines = code.splitlines()
    long_lines = [i + 1 for i, ln in enumerate(lines) if len(ln) > 100]
    if long_lines:
        issues.append({"type": "long_lines", "lines": long_lines})
    todos = [i + 1 for i, ln in enumerate(lines) if "TODO" in ln or "FIXME" in ln]
    if todos:
        issues.append({"type": "todos", "lines": todos})
    broad_except = [i + 1 for i, ln in enumerate(lines) if ln.strip().startswith("except:")]
    if broad_except:
        issues.append({"type": "broad_except", "lines": broad_except})
    if len(lines) > 20 and ('"""' not in code and "'''" not in code):
        issues.append({"type": "missing_module_docstring"})
    state["basic_issues"] = issues
    state["issues_count"] = len(issues)
    # optionally return a merged info (will be merged into state by engine)
    return {"next": "done_node"}
