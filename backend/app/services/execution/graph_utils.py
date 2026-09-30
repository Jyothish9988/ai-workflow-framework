"""Static graph analysis. `adjacency` maps node_id -> [{"target": id, "sourceHandle": handle}, ...]."""

EXIT_HANDLES = ("exit", "done", "after")   # loop handles that mean "leave the loop"


def _bfs(start: str, adjacency: dict) -> list[str]:
    """All nodes reachable from `start`, in breadth-first order."""
    seen, queue, order = set(), [start], []
    while queue:
        n = queue.pop(0)
        if n in seen:
            continue
        seen.add(n)
        order.append(n)
        queue.extend(e["target"] for e in adjacency.get(n, []))
    return order


def find_merge_node(if_node_id: str, adjacency: dict) -> str | None:
    """First node reachable from BOTH branches of an IF (where the branches rejoin)."""
    edges = adjacency.get(if_node_id, [])
    true_start = next((e["target"] for e in edges if e.get("sourceHandle") == "true"), None)
    false_start = next((e["target"] for e in edges if e.get("sourceHandle") == "false"), None)
    if not true_start or not false_start:
        return None
    false_set = set(_bfs(false_start, adjacency))
    return next((n for n in _bfs(true_start, adjacency) if n in false_set), None)


def loop_body_edges(loop_node_id: str, adjacency: dict) -> list[dict]:
    """Edges leaving the loop that start the body (i.e. not an exit handle)."""
    return [e for e in adjacency.get(loop_node_id, []) if e.get("sourceHandle") not in EXIT_HANDLES]


def find_loop_exit(loop_node_id: str, adjacency: dict) -> str | None:
    """Node to run after the loop finishes.
    1) an explicit exit/done/after handle wins;
    2) otherwise the first node reached from the body that is not part of the body."""
    for e in adjacency.get(loop_node_id, []):
        if e.get("sourceHandle") in EXIT_HANDLES:
            return e["target"]

    body_starts = [e["target"] for e in loop_body_edges(loop_node_id, adjacency)]
    body_nodes = {n for s in body_starts for n in _bfs(s, adjacency)}

    seen, queue = set(), list(body_starts)
    while queue:
        n = queue.pop(0)
        if n in seen:
            continue
        seen.add(n)
        for e in adjacency.get(n, []):
            if e["target"] not in body_nodes:
                return e["target"]
            queue.append(e["target"])
    return None
