from .graph_engine import create_graph

EXAMPLE_GRAPH = {
    "entry": "extract_functions",
    "nodes": {
        "extract_functions": {
            "fn": "extract_functions",
            "next": "check_complexity"
        },
        "check_complexity": {
            "fn": "check_complexity",
            "next": {"true": "detect_basic_issues", "false": "detect_basic_issues"},
            "meta": {
                "condition": "state.get('has_high_complexity', False) == True"
            }
        },
        "detect_basic_issues": {
            "fn": "detect_basic_issues",
            "next": "done_node"
        },
        "done_node": {
            "fn": None
        }
    }
}

def create_example_graph():
    """
    Create and return the example Option A graph id.
    """
    return create_graph(EXAMPLE_GRAPH)
