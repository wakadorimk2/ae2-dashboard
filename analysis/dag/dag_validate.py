from __future__ import annotations

import argparse
import glob
import sys
from collections import deque
from pathlib import Path
from typing import Dict, List, Tuple

import networkx as nx

REPO_ROOT = Path(__file__).resolve().parents[2]
COLLECTOR_ROOT = REPO_ROOT / "collector"
if str(COLLECTOR_ROOT) not in sys.path:
    sys.path.insert(0, str(COLLECTOR_ROOT))

from app.dag.graph import (
    DEFAULT_EDGES_PATH,
    DEFAULT_GROUPS_PATH,
    build_graph,
    load_yaml,
    topo_order,
    validate_graph,
)
from app.dag.scoring import score_expansion, score_mismatch, score_slowing
from app.dag.stats import NodeStats, build_stats_from_snapshots, parse_snapshot_with_ts


# ----------------------------
# Stats loading
# ----------------------------

def demo_stats(G: nx.DiGraph) -> Dict[str, NodeStats]:
    """
    Minimal synthetic stats to test the machinery.
    Replace this with real metrics loading later.
    """
    stats: Dict[str, NodeStats] = {n: NodeStats() for n in G.nodes}

    stats["chlorine_out"] = NodeStats(amount=50000, rate_short=120, rate_mid=130, volatility=5)
    stats["hydrogen_out"] = NodeStats(amount=80000, rate_short=150, rate_mid=160, volatility=6)

    stats["hcl_out"] = NodeStats(amount=20000, rate_short=20, rate_mid=90, volatility=12)

    stats["sulfuric_acid_out"] = NodeStats(amount=10000, rate_short=2, rate_mid=30, volatility=8)

    stats["ore_5x_chain"] = NodeStats(amount=0, rate_short=1, rate_mid=25, volatility=20)
    stats["ore_products"] = NodeStats(amount=5000, rate_short=5, rate_mid=40, volatility=15)

    stats["ethylene_out"] = NodeStats(amount=60000, rate_short=60, rate_mid=55, volatility=4)
    stats["hdpe_out"] = NodeStats(amount=25000, rate_short=18, rate_mid=20, volatility=2)

    stats["gunpowder_out"] = NodeStats(amount=9000, rate_short=10, rate_mid=12, volatility=9)

    return stats


def iter_jsonl_files(jsonl_dir: Path, pattern: str, max_files: int) -> list[Path]:
    paths = [Path(p) for p in glob.glob(str(jsonl_dir / pattern))]
    paths.sort(key=lambda p: p.stat().st_mtime)
    if max_files and len(paths) > max_files:
        paths = paths[-max_files:]
    return paths


def load_snapshots_from_files(
    files: list[Path],
    source: str | None = None,
) -> list[tuple[float, dict[str, float]]]:
    snapshots: list[tuple[float, dict[str, float]]] = []
    for fp in files:
        with fp.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                parsed = parse_snapshot_with_ts(line, source=source)
                if parsed is not None:
                    snapshots.append(parsed)

    snapshots.sort(key=lambda item: item[0])
    return snapshots


def iter_last_n_lines(path: Path, n: int):
    """Read a file and yield its last N non-empty lines."""
    buf = deque(maxlen=n)
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                buf.append(line)
    for line in buf:
        yield line


def top_k(items: List[Tuple[float, str]], k: int) -> List[Tuple[float, str]]:
    return sorted(items, key=lambda x: x[0], reverse=True)[:k]


def split_edge_id(edge_id: str) -> tuple[str, str]:
    parts = edge_id.split(" -> ", 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return edge_id, ""


# ----------------------------
# Main validation
# ----------------------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--groups", type=str, default=str(DEFAULT_GROUPS_PATH))
    ap.add_argument("--edges", type=str, default=str(DEFAULT_EDGES_PATH))
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--use-demo", action="store_true", help="Use synthetic stats")
    ap.add_argument("--jsonl", type=str, default=None, help="Path to ingest jsonl")
    ap.add_argument("--source", type=str, default=None, help="Filter jsonl records by source")
    ap.add_argument("--max-lines", type=int, default=200, help="Read last N jsonl lines")
    ap.add_argument("--short-min", type=float, default=10.0)
    ap.add_argument("--mid-min", type=float, default=60.0)
    ap.add_argument("--jsonl-dir", type=str, default=None)
    ap.add_argument("--glob", type=str, default="*.jsonl")
    ap.add_argument("--max-files", type=int, default=300)
    ap.add_argument("--debug", action="store_true")
    ap.add_argument("--debug-nodes", type=str, default="hydrogen_out,chlorine_out,sulfuric_acid_out,hcl_out")
    args = ap.parse_args()

    groups_path = Path(args.groups)
    edges_path = Path(args.edges)

    G = build_graph(groups_path, edges_path)

    # 1) DAG check
    is_dag = nx.is_directed_acyclic_graph(G)
    print(f"[DAG] is_dag={is_dag}  nodes={G.number_of_nodes()} edges={G.number_of_edges()}")
    if not is_dag:
        print("Graph is NOT a DAG. Showing cycles (first 3):")
        cycles = list(nx.simple_cycles(G))
        for cycle in cycles[:3]:
            print("  cycle:", " -> ".join(cycle))
        print("Tip: canonicalize small loops into a single node (e.g., substrate_pool).")
        return

    try:
        validate_graph(G)
    except ValueError as exc:
        print(f"Validation error: {exc}")
        return

    # 2) Topological order
    topo = topo_order(G)
    print("\n[Topological order] (first 25)")
    for node_id in topo[:25]:
        label = G.nodes[node_id].get("label", node_id)
        print(f"  - {node_id:20s} | {label}")

    # 3) Stats
    groups_doc = load_yaml(groups_path)
    groups_by_id = {g["id"]: g for g in groups_doc.get("groups", []) if "id" in g}

    if args.use_demo:
        stats = demo_stats(G)
    elif args.jsonl_dir:
        files = iter_jsonl_files(Path(args.jsonl_dir), args.glob, args.max_files)
        snapshots = load_snapshots_from_files(files, source=args.source)
        stats = build_stats_from_snapshots(
            groups=groups_doc,
            snapshots=snapshots,
            short_minutes=args.short_min,
            mid_minutes=args.mid_min,
        )
    elif args.jsonl:
        snapshots = []
        for line in iter_last_n_lines(Path(args.jsonl), args.max_lines):
            parsed = parse_snapshot_with_ts(line, source=args.source)
            if parsed is not None:
                snapshots.append(parsed)
        snapshots.sort(key=lambda item: item[0])
        stats = build_stats_from_snapshots(
            groups=groups_doc,
            snapshots=snapshots,
            short_minutes=args.short_min,
            mid_minutes=args.mid_min,
        )
    else:
        raise SystemExit("Run with --use-demo or provide --jsonl / --jsonl-dir.")

    def is_observed(node_id: str) -> bool:
        return node_id.endswith("_out")

    def has_members(node_id: str) -> bool:
        group_def = groups_by_id.get(node_id)
        if not group_def:
            return False
        fingerprints = (group_def.get("members") or {}).get("fingerprints") or []
        return len(fingerprints) > 0

    def tag_for_edge(upstream: str, downstream: str, downstream_stats: NodeStats) -> str:
        if (not is_observed(downstream)) and (not has_members(downstream)) and downstream_stats.amount == 0:
            return "NEW"
        return "IMBAL"

    if args.debug:
        print("\n[Debug: NodeStats]")
        for node_id in [x.strip() for x in args.debug_nodes.split(",") if x.strip()]:
            st = stats.get(node_id)
            if not st:
                print(f"  - {node_id}: (missing)")
                continue
            label = G.nodes[node_id].get("label", node_id)
            print(
                f"  - {node_id:20s} | {label:28s} | amount={st.amount:12.2f} "
                f"| short={st.rate_short:10.4f}/m | mid={st.rate_mid:10.4f}/m "
                f"| vol={st.volatility:8.4f}"
            )

    influence_map: Dict[str, int] = {}
    for node_id in G.nodes:
        influence_map[node_id] = len(nx.descendants(G, node_id))

    slowing = top_k(score_slowing(stats), args.k)

    mismatch_raw = score_mismatch(G, stats)
    mismatch: list[tuple[float, str]] = []
    for score, edge_id in mismatch_raw:
        upstream, downstream = split_edge_id(edge_id)
        if not upstream or not downstream:
            continue
        if not is_observed(upstream):
            continue
        downstream_stats = stats.get(downstream, NodeStats())
        tag = tag_for_edge(upstream, downstream, downstream_stats)
        mismatch.append((score, f"[{tag}]{edge_id}"))
    mismatch = top_k(mismatch, args.k)

    expansion = top_k(score_expansion(stats, influence_by_node=influence_map), args.k)

    def fmt_node(node_id: str) -> str:
        return G.nodes[node_id].get("label", node_id)

    print("\n[Suggestion: Slowing down] Top-K")
    for score, node_id in slowing:
        st = stats[node_id]
        print(
            f"  - {node_id:20s} | {fmt_node(node_id):30s} | score={score:8.2f} "
            f"| short={st.rate_short:7.2f}/m mid={st.rate_mid:7.2f}/m"
        )

    print("\n[Suggestion: Pipeline mismatch] Top-K (edge-based)")
    for score, edge_id in mismatch:
        print(f"  - {edge_id:45s} | score={score:8.2f}")

    print("\n[Suggestion: Expansion targets] Top-K")
    for score, node_id in expansion:
        st = stats[node_id]
        infl = influence_map.get(node_id, 0)
        print(
            f"  - {node_id:20s} | {fmt_node(node_id):30s} | score={score:8.2f} "
            f"| mid={st.rate_mid:7.2f}/m vol={st.volatility:6.2f} infl={infl}"
        )

    print("\nDone.")


if __name__ == "__main__":
    main()
