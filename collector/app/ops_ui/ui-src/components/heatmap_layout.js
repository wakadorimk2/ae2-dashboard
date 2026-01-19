// @ts-check

import { toNumber } from "./heatmap_model.js";

/** @typedef {import("../types.js").UiHeatmapEntry} UiHeatmapEntry */

/**
 * @param {Array<{ weight: number, item: UiHeatmapEntry }>} items
 * @param {number} width
 * @param {number} height
 * @returns {Array<{ x: number, y: number, w: number, h: number, item: UiHeatmapEntry }>}
 */
export function buildTreemap(items, width, height) {
  const w = toNumber(width, 0);
  const h = toNumber(height, 0);
  if (!Array.isArray(items) || items.length === 0 || w <= 0 || h <= 0) return [];

  const filtered = items
    .map(entry => ({ item: entry.item, weight: Math.max(0, toNumber(entry.weight, 0)) }))
    .filter(entry => entry.weight > 0);
  if (filtered.length === 0) return [];

  const total = filtered.reduce((acc, entry) => acc + entry.weight, 0);
  if (!Number.isFinite(total) || total <= 0) return [];

  const area = w * h;
  const nodes = filtered.map(entry => ({
    item: entry.item,
    area: area * (entry.weight / total),
  }));
  nodes.sort((a, b) => b.area - a.area);

  /** @type {Array<{ x: number, y: number, w: number, h: number, item: UiHeatmapEntry }>} */
  const tiles = [];
  let rect = { x: 0, y: 0, w, h };

  /**
   * @param {Array<{ area: number }>} row
   * @param {number} side
   * @returns {number}
   */
  function worst(row, side) {
    if (!row.length) return Infinity;
    let sum = 0;
    let max = 0;
    let min = Infinity;
    for (const r of row) {
      const a = toNumber(r.area, 0);
      sum += a;
      if (a > max) max = a;
      if (a < min) min = a;
    }
    if (sum <= 0 || min <= 0) return Infinity;
    const s2 = side * side;
    return Math.max((s2 * max) / (sum * sum), (sum * sum) / (s2 * min));
  }

  /**
   * @param {Array<{ area: number, item: UiHeatmapEntry }>} row
   */
  function layoutRow(row) {
    let sum = 0;
    for (const r of row) sum += toNumber(r.area, 0);
    if (sum <= 0) return;

    if (rect.w >= rect.h) {
      const rowHeight = sum / rect.w;
      let x = rect.x;
      for (const r of row) {
        const tileW = r.area / rowHeight;
        tiles.push({ x, y: rect.y, w: tileW, h: rowHeight, item: r.item });
        x += tileW;
      }
      rect = { x: rect.x, y: rect.y + rowHeight, w: rect.w, h: rect.h - rowHeight };
    } else {
      const rowWidth = sum / rect.h;
      let y = rect.y;
      for (const r of row) {
        const tileH = r.area / rowWidth;
        tiles.push({ x: rect.x, y, w: rowWidth, h: tileH, item: r.item });
        y += tileH;
      }
      rect = { x: rect.x + rowWidth, y: rect.y, w: rect.w - rowWidth, h: rect.h };
    }
  }

  /** @type {Array<{ area: number, item: UiHeatmapEntry }>} */
  let row = [];
  const remaining = nodes.slice();
  while (remaining.length > 0) {
    const next = remaining[0];
    const side = Math.min(rect.w, rect.h);
    if (row.length === 0 || worst(row.concat(next), side) <= worst(row, side)) {
      row.push(next);
      remaining.shift();
      continue;
    }
    layoutRow(row);
    row = [];
  }
  if (row.length) layoutRow(row);

  return tiles;
}
