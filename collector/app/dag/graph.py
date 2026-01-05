from __future__ import annotations

from pathlib import Path

import networkx as nx
import yaml

DEFAULT_DEFS_DIR = Path(__file__).resolve().parent / "defs"
DEFAULT_GROUPS_PATH = DEFAULT_DEFS_DIR / "groups.yaml"
DEFAULT_EDGES_PATH = DEFAULT_DEFS_DIR / "edges.yaml"


def load_yaml(path: Path | str) -> dict:
    """Load a YAML file and return its top-level mapping."""
    path = Path(path)
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def build_graph(groups_yaml_path: Path | str, edges_yaml_path: Path | str) -> nx.DiGraph:
    """
    Build a directed graph from group/edge definitions.

    Notes:
        - Metadata about duplicate IDs and missing nodes is stored in G.graph.
        - Nodes created only by edges are marked with _from_groups=False.
    """
    groups_doc = load_yaml(groups_yaml_path)
    edges_doc = load_yaml(edges_yaml_path)

    groups_list = groups_doc.get("groups", []) or []
    seen_ids: set[str] = set()
    dup_ids: set[str] = set()
    for group in groups_list:
        group_id = group.get("id")
        if group_id is None:
            continue
        if group_id in seen_ids:
            dup_ids.add(group_id)
        seen_ids.add(group_id)

    graph = nx.DiGraph()
    for group in groups_list:
        group_id = group.get("id")
        if group_id is None:
            continue
        graph.add_node(group_id, **group, _from_groups=True)

    missing_nodes: set[str] = set()
    for edge in edges_doc.get("edges", []) or []:
        upstream = edge.get("from")
        downstream = edge.get("to")
        if upstream is None or downstream is None:
            continue
        if upstream not in seen_ids:
            missing_nodes.add(upstream)
        if downstream not in seen_ids:
            missing_nodes.add(downstream)
        if upstream not in graph:
            graph.add_node(upstream, id=upstream, label=upstream, kind="unknown", _from_groups=False)
        if downstream not in graph:
            graph.add_node(downstream, id=downstream, label=downstream, kind="unknown", _from_groups=False)
        graph.add_edge(upstream, downstream, **edge)

    graph.graph["group_ids"] = sorted(seen_ids)
    graph.graph["duplicate_group_ids"] = sorted(dup_ids)
    graph.graph["missing_node_ids"] = sorted(missing_nodes)

    return graph


def validate_graph(graph: nx.DiGraph) -> None:
    """Validate a graph built from DAG definitions."""
    dup_ids = graph.graph.get("duplicate_group_ids", []) or []
    if dup_ids:
        raise ValueError(f"Duplicate group ids: {', '.join(dup_ids)}")

    missing_nodes = graph.graph.get("missing_node_ids", []) or []
    if missing_nodes:
        raise ValueError(f"Edges reference missing nodes: {', '.join(missing_nodes)}")

    if not nx.is_directed_acyclic_graph(graph):
        cycles = list(nx.simple_cycles(graph))
        message = "Graph is not a DAG."
        if cycles:
            preview = [" -> ".join(cycle) for cycle in cycles[:3]]
            message = f"{message} Cycles: {', '.join(preview)}"
        raise ValueError(message)


def topo_order(graph: nx.DiGraph) -> list[str]:
    """Return the topological order of the graph's nodes."""
    return list(nx.topological_sort(graph))
