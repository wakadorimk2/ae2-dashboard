from __future__ import annotations

import math
from typing import Mapping

import networkx as nx

from app.dag.stats import NodeStats


def score_slowing(
    stats_by_node: Mapping[str, NodeStats],
    eps: float = 1e-6,
) -> list[tuple[float, str]]:
    """
    Score nodes where short-rate has slowed relative to the mid-rate.
    Returns a list of (score, node_id) in descending score order.
    """
    results: list[tuple[float, str]] = []
    for node_id, stats in stats_by_node.items():
        if stats.rate_mid <= 0:
            continue
        ratio = stats.rate_short / max(stats.rate_mid, eps)
        if ratio >= 1.0:
            continue
        score = (1.0 - ratio) * stats.rate_mid
        if score > 0:
            results.append((score, node_id))
    return sorted(results, key=lambda item: item[0], reverse=True)


def score_mismatch(
    graph: nx.DiGraph,
    stats_by_node: Mapping[str, NodeStats],
) -> list[tuple[float, str]]:
    """
    Score edges where upstream short-rate exceeds downstream short-rate.
    Returns a list of (score, "upstream -> downstream") in descending order.
    """
    results: list[tuple[float, str]] = []
    for upstream, downstream in graph.edges:
        stats_up = stats_by_node.get(upstream, NodeStats())
        stats_down = stats_by_node.get(downstream, NodeStats())
        if stats_up.rate_short <= 0:
            continue
        gap = stats_up.rate_short - stats_down.rate_short
        score = max(0.0, gap)
        if score > 0:
            results.append((score, f"{upstream} -> {downstream}"))
    return sorted(results, key=lambda item: item[0], reverse=True)


def score_expansion(
    stats_by_node: Mapping[str, NodeStats],
    influence_by_node: Mapping[str, int] | None = None,
) -> list[tuple[float, str]]:
    """
    Score nodes that look stable and growing with room to expand.
    Returns a list of (score, node_id) in descending score order.
    """
    results: list[tuple[float, str]] = []
    for node_id, stats in stats_by_node.items():
        if stats.rate_mid <= 0:
            continue

        stability = 1.0 / (1.0 + max(0.0, stats.volatility))

        target = 20.0
        spread = 25.0
        medium_pref = math.exp(-((stats.rate_mid - target) ** 2) / (2.0 * (spread**2)))

        influence = 0
        if influence_by_node is not None:
            influence = influence_by_node.get(node_id, 0)
        infl_bonus = math.log1p(max(0, influence))

        score = 100.0 * stability * medium_pref * (1.0 + 0.3 * infl_bonus)
        if score > 0:
            results.append((score, node_id))

    return sorted(results, key=lambda item: item[0], reverse=True)
