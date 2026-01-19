// @ts-check

import { getDisplayName } from "../i18n.js";
import { toPerMinute } from "../scale_bridge.js";
import { DELTA_UNIT, state } from "../state.js";

/** @typedef {import("../types.js").UiTopFlatEntry} UiTopFlatEntry */
/** @typedef {import("../types.js").UiHeatmapEntry} UiHeatmapEntry */

export const OTHERS_RAW = "__others__";

/**
 * @param {unknown} value
 * @param {number} fallback
 * @returns {number}
 */
export function toNumber(value, fallback) {
  return (typeof value === "number" && Number.isFinite(value)) ? value : fallback;
}

/**
 * @param {UiTopFlatEntry} entry
 * @returns {UiHeatmapEntry | null}
 */
export function coerceEntry(entry) {
  if (!entry || typeof entry !== "object") return null;
  const raw = entry.raw_name || entry.display_name || "-";
  const name = getDisplayName(raw);
  const amount = Math.max(0, toNumber(entry.amount, 0));
  const growth = toNumber(entry.growth, 0);
  const decrease = toNumber(entry.decrease, 0);
  const delta = toNumber(toPerMinute(growth - decrease, DELTA_UNIT), 0);
  return { raw, name, amount, delta, entry };
}

/**
 * @param {UiHeatmapEntry[]} list
 * @returns {UiHeatmapEntry[]}
 */
export function selectHeatmapEntries(list) {
  const entries = Array.isArray(list) ? list.slice() : [];
  if (entries.length === 0) return [];
  entries.sort((a, b) => {
    const aScore = toNumber(a.amount, 0);
    const bScore = toNumber(b.amount, 0);
    return bScore - aScore;
  });
  const totalAmount = entries.reduce((sum, entry) => {
    return sum + Math.max(0, toNumber(entry.amount, 0));
  }, 0);
  const maxCount = Math.max(1, toNumber(state.heatmapCount, 120));
  const count = Math.min(maxCount, entries.length);
  let top = entries.slice(0, count);
  let rest = entries.slice(count);
  const minNamed = 12;
  const microRatio = 0.002;
  const microTailCount = 10;
  const microTailRatio = 0.01;
  if (totalAmount > 0 && top.length > minNamed) {
    const microCandidates = new Set();
    const microMin = totalAmount * microRatio;
    for (let i = 0; i < top.length; i++) {
      if (toNumber(top[i].amount, 0) < microMin) microCandidates.add(i);
    }
    let tailSum = 0;
    for (let i = top.length - 1; i >= 0 && (top.length - i) <= microTailCount; i--) {
      tailSum += Math.max(0, toNumber(top[i].amount, 0));
      if (tailSum <= totalAmount * microTailRatio) {
        microCandidates.add(i);
      } else {
        break;
      }
    }
    const maxRemovable = top.length - minNamed;
    if (microCandidates.size > 0 && maxRemovable > 0) {
      const kept = [];
      const moved = [];
      let removed = 0;
      for (let i = top.length - 1; i >= 0; i--) {
        const entry = top[i];
        if (removed < maxRemovable && microCandidates.has(i)) {
          moved.push(entry);
          removed += 1;
        } else {
          kept.push(entry);
        }
      }
      kept.reverse();
      moved.reverse();
      if (moved.length > 0) {
        top = kept;
        rest = moved.concat(rest);
      }
    }
  }
  if (rest.length === 0) return top;

  let otherAmount = 0;
  let otherDelta = 0;
  let otherGrowth = 0;
  let otherDecrease = 0;
  for (const entry of rest) {
    otherAmount += toNumber(entry.amount, 0);
    otherDelta += toNumber(entry.delta, 0);
    otherGrowth += toNumber(entry.entry?.growth, 0);
    otherDecrease += toNumber(entry.entry?.decrease, 0);
  }
  const otherCount = rest.length;
  if (otherAmount <= 0) return top;
  const otherName = `Others (n=${otherCount})`;
  top.push({
    raw: OTHERS_RAW,
    name: otherName,
    amount: otherAmount,
    delta: otherDelta,
    entry: {
      raw_name: OTHERS_RAW,
      display_name: otherName,
      amount: otherAmount,
      growth: otherGrowth,
      decrease: otherDecrease,
      net: otherGrowth - otherDecrease,
    },
  });
  return top;
}
