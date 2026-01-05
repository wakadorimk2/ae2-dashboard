from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
import json
from statistics import pstdev


@dataclass
class NodeStats:
    amount: float = 0.0
    rate_short: float = 0.0  # per minute
    rate_mid: float = 0.0  # per minute
    volatility: float = 0.0  # stddev of per-interval short rates
    capacity: float | None = None


Snapshot = tuple[float, dict[str, float]]


def parse_snapshot(jsonl_line: str) -> dict[str, float]:
    """Parse a JSONL snapshot line into fingerprint amounts."""
    obj = json.loads(jsonl_line)
    return _amounts_from_entries(obj.get("entries", []) or [])


def parse_snapshot_with_ts(jsonl_line: str, source: str | None = None) -> Snapshot | None:
    """
    Parse a JSONL snapshot line into (timestamp, fingerprint amounts).

    Returns None when a source filter is provided and does not match.
    """
    obj = json.loads(jsonl_line)
    if source is not None and obj.get("source") != source:
        return None
    ts = float(obj["ts"])
    return ts, _amounts_from_entries(obj.get("entries", []) or [])


def build_stats_from_snapshots(
    groups: Mapping[str, object] | Sequence[Mapping[str, object]],
    snapshots: Sequence[Snapshot],
    short_minutes: float = 10.0,
    mid_minutes: float = 60.0,
) -> dict[str, NodeStats]:
    """
    Compute NodeStats for each group definition based on timed snapshots.

    Args:
        groups: YAML mapping with a "groups" key or a list of group dicts.
        snapshots: Sequence of (timestamp, fingerprint->amount) entries.
        short_minutes: Window size for short rate.
        mid_minutes: Window size for mid rate.
    """
    if len(snapshots) < 2:
        raise ValueError(f"Not enough snapshots (need >=2). Got {len(snapshots)}.")

    group_list = _normalize_groups(groups)
    groups_by_id = {group["id"]: group for group in group_list if "id" in group}

    ordered = sorted(snapshots, key=lambda item: item[0])
    ts_now = ordered[-1][0]

    short_snaps = _windowed(ordered, ts_now, short_minutes)
    mid_snaps = _windowed(ordered, ts_now, mid_minutes)

    stats: dict[str, NodeStats] = {}
    for node_id, group_def in groups_by_id.items():
        t_short, v_short = _series(group_def, short_snaps)
        t_mid, v_mid = _series(group_def, mid_snaps)

        amount_now = v_short[-1] if v_short else 0.0
        rate_short = _compute_rate_per_min(t_short, v_short) if len(t_short) >= 2 else 0.0
        rate_mid = _compute_rate_per_min(t_mid, v_mid) if len(t_mid) >= 2 else 0.0
        volatility = _compute_short_volatility(t_short, v_short) if len(t_short) >= 3 else 0.0

        stats[node_id] = NodeStats(
            amount=amount_now,
            rate_short=rate_short,
            rate_mid=rate_mid,
            volatility=volatility,
            capacity=None,
        )

    return stats


def _normalize_groups(
    groups: Mapping[str, object] | Sequence[Mapping[str, object]],
) -> list[Mapping[str, object]]:
    if isinstance(groups, Mapping):
        return list(groups.get("groups", []) or [])
    return list(groups)


def _amounts_from_entries(entries: Iterable[Mapping[str, object]]) -> dict[str, float]:
    amounts: dict[str, float] = defaultdict(float)
    for entry in entries:
        fingerprint = entry.get("fingerprint")
        amount = entry.get("amount")
        if fingerprint is None or amount is None:
            continue
        amounts[str(fingerprint)] += float(amount)
    return dict(amounts)


def _group_amount_from_snapshot(group_def: Mapping[str, object], fp_amount: dict[str, float]) -> float:
    members = group_def.get("members") or {}
    fingerprints = members.get("fingerprints") or []
    total = 0.0
    for fingerprint in fingerprints:
        total += fp_amount.get(fingerprint, 0.0)
    return total


def _series(
    group_def: Mapping[str, object],
    snapshots: Iterable[Snapshot],
) -> tuple[list[float], list[float]]:
    t_list: list[float] = []
    v_list: list[float] = []
    last_val: float | None = None

    members = group_def.get("members") or {}
    fingerprints = members.get("fingerprints") or []

    for ts, fp_amount in snapshots:
        present = any(fingerprint in fp_amount for fingerprint in fingerprints)
        if present:
            val = _group_amount_from_snapshot(group_def, fp_amount)
            last_val = val
        else:
            if last_val is None:
                continue
            val = last_val
        t_list.append(ts)
        v_list.append(val)

    return t_list, v_list


def _windowed(
    snapshots: Sequence[Snapshot],
    ts_now: float,
    minutes: float,
) -> list[Snapshot]:
    t_min = ts_now - minutes * 60.0
    return [(ts, amounts) for ts, amounts in snapshots if ts >= t_min]


def _compute_rate_per_min(times: Sequence[float], values: Sequence[float]) -> float:
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


def _compute_short_volatility(times: Sequence[float], values: Sequence[float]) -> float:
    if len(times) < 3:
        return 0.0
    rates: list[float] = []
    for i in range(1, len(times)):
        dt = times[i] - times[i - 1]
        if dt <= 0:
            continue
        rates.append((values[i] - values[i - 1]) / (dt / 60.0))
    if len(rates) < 2:
        return 0.0
    return float(pstdev(rates))
