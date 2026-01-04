from __future__ import annotations

import glob
import argparse
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import yaml
import networkx as nx

import json
from collections import defaultdict, deque
from statistics import pstdev


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
# Stats loading
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

def iter_jsonl_files(jsonl_dir: Path, pattern: str, max_files: int) -> list[Path]:
    paths = [Path(p) for p in glob.glob(str(jsonl_dir / pattern))]
    # sort by mtime as a reasonable proxy; ts sort happens after parsing
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
        # each file has 1 line (your case), but support multi-line just in case
        with fp.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parsed = parse_snapshot(line, source=source)
                if parsed is not None:
                    snapshots.append(parsed)

    snapshots.sort(key=lambda x: x[0])  # by ts
    return snapshots

def iter_last_n_lines(path: Path, n: int):
    """
    Simple: read file and keep last n lines.
    For huge files, you can optimize later.
    """
    buf = deque(maxlen=n)
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                buf.append(line)
    for line in buf:
        yield line

def parse_snapshot(line: str, source: str | None = None) -> tuple[float, dict[str, float]] | None:
    """
    Returns (ts, {fingerprint: amount_sum}) for one jsonl record.
    """
    obj = json.loads(line)
    if source is not None and obj.get("source") != source:
        return None

    ts = float(obj["ts"])
    fp_amount: dict[str, float] = defaultdict(float)

    for e in obj.get("entries", []) or []:
        fp = e.get("fingerprint")
        amt = e.get("amount")
        if fp is None or amt is None:
            continue
        # amount could be int/float; sum duplicates
        fp_amount[fp] += float(amt)

    return ts, dict(fp_amount)

def group_amount_from_snapshot(group_def: dict, fp_amount: dict[str, float]) -> float:
    members = (group_def.get("members") or {})
    fps = members.get("fingerprints") or []
    total = 0.0
    for fp in fps:
        total += fp_amount.get(fp, 0.0)
    return total

def compute_rate_per_min(times, values):
    if len(times) < 3:
        return 0.0
    t_last = times[-1]
    v_last = values[-1]
    prev_vals = values[:-1]
    v_base = sum(prev_vals) / len(prev_vals)
    dt = t_last - times[0]
    if dt <= 0:
        return 0.0
    return (v_last - v_base) / (dt / 60.0)


def compute_short_volatility(times: list[float], values: list[float]) -> float:
    """
    Volatility = stddev of per-interval rate (per minute).
    """
    if len(times) < 3:
        return 0.0
    rates = []
    for i in range(1, len(times)):
        dt = times[i] - times[i - 1]
        if dt <= 0:
            continue
        rates.append((values[i] - values[i - 1]) / (dt / 60.0))
    if len(rates) < 2:
        return 0.0
    return float(pstdev(rates))

def build_stats_from_snapshots(
    G: nx.DiGraph,
    groups_doc: dict,
    snapshots: list[tuple[float, dict[str, float]]],
    short_minutes: float,
    mid_minutes: float,
) -> dict[str, NodeStats]:
    if len(snapshots) < 2:
        raise ValueError(f"Not enough snapshots (need >=2). Got {len(snapshots)}.")

    # (以下は今の build_stats_from_jsonl と同じ)
    ts_now = snapshots[-1][0]

    def windowed(minutes: float):
        t_min = ts_now - minutes * 60.0
        return [(t, m) for (t, m) in snapshots if t >= t_min]

    short_snaps = windowed(short_minutes)
    mid_snaps = windowed(mid_minutes)

    groups_by_id = {g["id"]: g for g in groups_doc.get("groups", [])}

    stats: dict[str, NodeStats] = {}
    for node in G.nodes:
        gdef = groups_by_id.get(node, {"id": node, "members": {"fingerprints": []}})

        def series(snaps):
            t_list = []
            v_list = []
            last_val = None

            for t, fp_amount in snaps:
                # 現snapshotにメンバーが1つでも載ってるか
                members = (gdef.get("members") or {}).get("fingerprints") or []
                present = any(fp in fp_amount for fp in members)

                if present:
                    val = group_amount_from_snapshot(gdef, fp_amount)
                    last_val = val
                else:
                    # 欠損なら前回値を維持（前回が無ければスキップでもOK）
                    if last_val is None:
                        continue
                    val = last_val

                t_list.append(t)
                v_list.append(val)

            return t_list, v_list

        t_s, v_s = series(short_snaps)
        t_m, v_m = series(mid_snaps)

        amount_now = v_s[-1] if v_s else 0.0
        rate_short = compute_rate_per_min(t_s, v_s) if len(t_s) >= 2 else 0.0
        rate_mid = compute_rate_per_min(t_m, v_m) if len(t_m) >= 2 else 0.0
        vol = compute_short_volatility(t_s, v_s) if len(t_s) >= 3 else 0.0

        stats[node] = NodeStats(
            amount=amount_now,
            rate_short=rate_short,
            rate_mid=rate_mid,
            volatility=vol,
            capacity=None,
        )

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
    groups_doc = load_yaml(Path(args.groups))
    groups_by_id = {g["id"]: g for g in groups_doc.get("groups", [])}

    if args.use_demo:
        stats = demo_stats(G)
    elif args.jsonl_dir:
        files = iter_jsonl_files(Path(args.jsonl_dir), args.glob, args.max_files)
        snapshots = load_snapshots_from_files(files, source=args.source)
        stats = build_stats_from_snapshots(
            G=G,
            groups_doc=groups_doc,
            snapshots=snapshots,
            short_minutes=args.short_min,
            mid_minutes=args.mid_min,
        )
    elif args.jsonl:
        # 既存の単一ファイル対応も残すならここで snapshots にしてから呼ぶ
        snapshots = []
        for line in iter_last_n_lines(Path(args.jsonl), args.max_lines):
            parsed = parse_snapshot(line, source=args.source)
            if parsed is not None:
                snapshots.append(parsed)
        snapshots.sort(key=lambda x: x[0])
        stats = build_stats_from_snapshots(G, groups_doc, snapshots, args.short_min, args.mid_min)
    else:
        raise SystemExit("Run with --use-demo or provide --jsonl / --jsonl-dir.")
    
    
    # ----------------------------
    # Helpers
    # ----------------------------
    def is_observed(node_id: str) -> bool:
        return node_id.endswith("_out")  # まずはこれでOK

    def has_members(node_id: str) -> bool:
        gdef = groups_by_id.get(node_id)
        if not gdef:
            return False
        fps = (gdef.get("members") or {}).get("fingerprints") or []
        return len(fps) > 0

    def tag_for_edge(u: str, v: str, sv: NodeStats) -> str:
        # 下流が工程っぽくて、観測できてないなら「未着手」扱い
        if (not is_observed(v)) and (not has_members(v)) and sv.amount == 0:
            return "NEW"
        return "IMBAL"

    if args.debug:
        print("\n[Debug: NodeStats]")
        for n in [x.strip() for x in args.debug_nodes.split(",") if x.strip()]:
            st = stats.get(n)
            if not st:
                print(f"  - {n}: (missing)")
                continue
            label = G.nodes[n].get("label", n)
            print(f"  - {n:20s} | {label:28s} | amount={st.amount:12.2f} | short={st.rate_short:10.4f}/m | mid={st.rate_mid:10.4f}/m | vol={st.volatility:8.4f}")

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
        if not is_observed(u):
            continue  # 上流だけ観測点ならOK（下流は工程でもOK）
        su = stats.get(u, NodeStats())
        sv = stats.get(v, NodeStats())
        s = score_mismatch(u, v, su, sv)
        tag = tag_for_edge(u, v, sv)
        if s > 0:
            mismatch.append((f"[{tag}]{u} -> {v}", s))
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
