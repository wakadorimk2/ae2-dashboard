from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import yaml
import networkx as nx


# ----------------------------
# Data model
# ----------------------------

@dataclass
class NodeStats:
    amount: float = 0.0
    rate_short: float = 0.0     # per minute
    rate_mid: float = 0.0       # per minute
    volatility: float = 0.0     # arbitrary scale (e.g., stddev of rate_short)
    capacity: Optional[float] = None


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_graph(groups_yaml: Path, edges_yaml: Path) -> Tuple[nx.DiGraph, Dict[str, dict]]:
    groups_doc = load_yaml(groups_yaml)
    edges_doc = load_yaml(edges_yaml)

    groups = {g["id"]: g for g in groups_doc.get("groups", [])}

    G = nx.DiGraph()
    for gid, g in groups.items():
        G.add_node(gid, **g)

    for e in edges_doc.get("edges", []):
        u, v = e["from"], e["to"]
        if u not in G:
            G.add_node(u, id=u, label=u, kind="unknown")
        if v not in G:
            G.add_node(v, id=v, label=v, kind="unknown")
        G.add_edge(u, v, **e)

    return G, groups


# ----------------------------
# Stats loading (stub)
# ----------------------------

def demo_stats(G: nx.DiGraph) -> Dict[str, NodeStats]:
    """
    Minimal synthetic stats to test the machinery.
    Replace this with real metrics loading later.
    """
    # Make something interesting:
    # - chlorine/hydrogen healthy
    # - hcl slowing
    # - ore5x chain "mismatch" due to lacking acid
    # - hdpe stable and medium growth
    stats: Dict[str, NodeStats] = {n: NodeStats() for n in G.nodes}

    # Base signals
    stats["chlorine_out"] = NodeStats(amount=50000, rate_short=120, rate_mid=130, volatility=5)
    stats["hydrogen_out"] = NodeStats(amount=80000, rate_short=150, rate_mid=160, volatility=6)

    # HCl: mid was good but short dropped -> slowing
    stats["hcl_out"] = NodeStats(amount=20000, rate_short=20, rate_mid=90, volatility=12)

    # Sulfuric acid: almost stalled
    stats["sulfuric_acid_out"] = NodeStats(amount=10000, rate_short=2, rate_mid=30, volatility=8)

    # Ore 5x chain depends on acid -> down
    stats["ore_5x_chain"] = NodeStats(amount=0, rate_short=1, rate_mid=25, volatility=20)
    stats["ore_products"] = NodeStats(amount=5000, rate_short=5, rate_mid=40, volatility=15)

    # HDPE: stable, medium growth -> good expansion target
    stats["ethylene_out"] = NodeStats(amount=60000, rate_short=60, rate_mid=55, volatility=4)
    stats["hdpe_out"] = NodeStats(amount=25000, rate_short=18, rate_mid=20, volatility=2)

    # Gunpowder: random-ish
    stats["gunpowder_out"] = NodeStats(amount=9000, rate_short=10, rate_mid=12, volatility=9)

    return stats


# ----------------------------
# Scoring
# ----------------------------

def score_slowing(stats: NodeStats, eps: float = 1e-6) -> float:
    """
    Higher => more 'slowing down' worth attention.
    """
    if stats.rate_mid <= 0:
        return 0.0
    ratio = stats.rate_short / max(stats.rate_mid, eps)
    if ratio >= 1.0:
        return 0.0
    # Weight by how meaningful the mid-rate was
    return (1.0 - ratio) * stats.rate_mid


def score_expansion(stats: NodeStats, influence: int) -> float:
    """
    Higher => good 'fun to expand' target.
    - stable (low volatility)
    - medium positive mid rate
    - plus influence bonus (downstream size)
    """
    if stats.rate_mid <= 0:
        return 0.0

    # Stability factor: smaller volatility -> higher score
    stability = 1.0 / (1.0 + max(0.0, stats.volatility))

    # Prefer medium rates: peak around ~20 per min (tune later)
    target = 20.0
    spread = 25.0
    mid = stats.rate_mid
    medium_pref = math.exp(-((mid - target) ** 2) / (2.0 * (spread ** 2)))

    # Influence bonus: log to avoid dominating
    infl = math.log1p(max(0, influence))

    return 100.0 * stability * medium_pref * (1.0 + 0.3 * infl)


def score_mismatch(edge_u: str, edge_v: str, stats_u: NodeStats, stats_v: NodeStats) -> float:
    """
    Higher => upstream growing but downstream not.
    """
    up = stats_u.rate_short
    down = stats_v.rate_short
    if up <= 0:
        return 0.0
    gap = up - down
    return max(0.0, gap)


def top_k(items: List[Tuple[str, float]], k: int) -> List[Tuple[str, float]]:
    return sorted(items, key=lambda x: x[1], reverse=True)[:k]


# ----------------------------
# Main validation
# ----------------------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--groups", type=str, default="groups.yaml")
    ap.add_argument("--edges", type=str, default="edges.yaml")
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--use-demo", action="store_true", help="Use synthetic stats")
    args = ap.parse_args()

    G, groups = build_graph(Path(args.groups), Path(args.edges))

    # 1) DAG check
    is_dag = nx.is_directed_acyclic_graph(G)
    print(f"[DAG] is_dag={is_dag}  nodes={G.number_of_nodes()} edges={G.number_of_edges()}")
    if not is_dag:
        print("Graph is NOT a DAG. Showing cycles (first 3):")
        cycles = list(nx.simple_cycles(G))
        for c in cycles[:3]:
            print("  cycle:", " -> ".join(c))
        print("Tip: canonicalize small loops into a single node (e.g., substrate_pool).")
        return

    # 2) Topological order
    topo = list(nx.topological_sort(G))
    print("\n[Topological order] (first 25)")
    for n in topo[:25]:
        label = G.nodes[n].get("label", n)
        print(f"  - {n:20s} | {label}")

    # 3) Stats
    if args.use_demo:
        stats = demo_stats(G)
    else:
        # Placeholder: integrate your real metrics here
        # Expect a json mapping node_id -> NodeStats fields, etc.
        raise SystemExit("Provide real stats loader or run with --use-demo")

    # Precompute influence: number of downstream nodes
    influence_map: Dict[str, int] = {}
    for n in G.nodes:
        influence_map[n] = len(nx.descendants(G, n))

    # 4) Suggestions
    # A) Slowing down
    slowing = []
    for n, st in stats.items():
        s = score_slowing(st)
        if s > 0:
            slowing.append((n, s))
    slowing = top_k(slowing, args.k)

    # B) Mismatch (edge-based)
    mismatch = []
    for u, v in G.edges:
        su = stats.get(u, NodeStats())
        sv = stats.get(v, NodeStats())
        s = score_mismatch(u, v, su, sv)
        if s > 0:
            mismatch.append((f"{u} -> {v}", s))
    mismatch = top_k(mismatch, args.k)

    # C) Expansion
    expansion = []
    for n, st in stats.items():
        s = score_expansion(st, influence_map.get(n, 0))
        if s > 0:
            expansion.append((n, s))
    expansion = top_k(expansion, args.k)

    def fmt_node(n: str) -> str:
        return G.nodes[n].get("label", n)

    print("\n[Suggestion: Slowing down] Top-K")
    for n, s in slowing:
        st = stats[n]
        print(f"  - {n:20s} | {fmt_node(n):30s} | score={s:8.2f} | short={st.rate_short:7.2f}/m mid={st.rate_mid:7.2f}/m")

    print("\n[Suggestion: Pipeline mismatch] Top-K (edge-based)")
    for e, s in mismatch:
        print(f"  - {e:45s} | score={s:8.2f}")

    print("\n[Suggestion: Expansion targets] Top-K")
    for n, s in expansion:
        st = stats[n]
        infl = influence_map.get(n, 0)
        print(f"  - {n:20s} | {fmt_node(n):30s} | score={s:8.2f} | mid={st.rate_mid:7.2f}/m vol={st.volatility:6.2f} infl={infl}")

    print("\nDone.")


if __name__ == "__main__":
    main()
