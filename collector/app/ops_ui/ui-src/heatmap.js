// @ts-check

import { getDisplayName } from "./i18n.js";
import { getIconUrl } from "./icons.js";
import { formatValue, unitFor } from "./format.js";
import { toPerMinute } from "./scale_bridge.js";
import { DELTA_UNIT, state } from "./state.js";

/** @typedef {import("./types.js").UiTopFlatEntry} UiTopFlatEntry */
/** @typedef {import("./types.js").UiTopFlat} UiTopFlat */
/** @typedef {import("./types.js").UiHeatmapEntry} UiHeatmapEntry */
/** @typedef {UiHeatmapEntry & { deltaScaled: number }} UiHeatmapEntryScaled */

const HEATMAP_EPS = 0.02;

/**
 * @param {unknown} value
 * @param {number} fallback
 * @returns {number}
 */
function toNumber(value, fallback) {
  return (typeof value === "number" && Number.isFinite(value)) ? value : fallback;
}

/**
 * @param {number} value
 * @param {number} min
 * @param {number} max
 * @returns {number}
 */
function clamp(value, min, max) {
  const v = toNumber(value, min);
  return Math.min(max, Math.max(min, v));
}

/**
 * @param {UiTopFlatEntry} entry
 * @returns {UiHeatmapEntry | null}
 */
function coerceEntry(entry) {
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
 * @param {number} deltaNorm
 * @returns {string}
 */
function colorForDelta(deltaNorm) {
  const v = clamp(deltaNorm, -1, 1);
  const t = Math.abs(v);
  const hue = v >= 0 ? 140 : 5;
  const sat = Math.round(25 + 55 * t);
  const light = Math.round(22 + 18 * (1 - t));
  return `hsl(${hue}, ${sat}%, ${light}%)`;
}

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

/**
 * @param {UiHeatmapEntry[]} list
 * @returns {UiHeatmapEntry[]}
 */
function selectHeatmapEntries(list) {
  const entries = Array.isArray(list) ? list.slice() : [];
  if (entries.length === 0) return [];
  const sortMode = state.heatmapSort;
  entries.sort((a, b) => {
    const aScore = sortMode === "delta" ? Math.abs(a.delta) : a.amount;
    const bScore = sortMode === "delta" ? Math.abs(b.delta) : b.amount;
    return bScore - aScore;
  });
  const maxCount = Math.max(1, state.heatmapCount);
  const count = Math.min(maxCount, entries.length);
  return entries.slice(0, count);
}

/**
 * @param {HTMLElement} container
 * @param {Array<{ x: number, y: number, w: number, h: number, item: UiHeatmapEntryScaled }>} tiles
 * @param {string} unit
 * @param {string} kind
 */
function renderTiles(container, tiles, unit, kind) {
  const frag = document.createDocumentFragment();
  for (const tile of tiles) {
    const entry = tile.item;
    const amount = toNumber(entry.amount, 0);
    const delta = toNumber(entry.delta, 0);
    const deltaScaled = toNumber(entry.deltaScaled, 0);
    const displayName = entry.name || "-";

    const el = document.createElement("div");
    el.className = "heatmap-tile";
    el.dataset.id = `${kind}:${entry.raw}`;
    el.tabIndex = 0;
    const w = Math.max(0, tile.w);
    const h = Math.max(0, tile.h);
    el.style.left = `${tile.x}px`;
    el.style.top = `${tile.y}px`;
    el.style.width = `${w}px`;
    el.style.height = `${h}px`;
    el.style.setProperty("--tile-bg", colorForDelta(deltaScaled));

    if (w < 44 || h < 30) {
      el.classList.add("tiny");
    } else if (w < 80 || h < 42) {
      el.classList.add("small");
    }

    const deltaText = `${delta > 0 ? "+" : ""}${formatValue(delta)}`;
    el.title = `${displayName}\nAmount: ${formatValue(amount)} ${unit}\nDelta: ${deltaText} /min`;

    const showLabel = w >= 48 && h >= 30;
    if (showLabel) {
      const label = document.createElement("div");
      label.className = "heatmap-label";
      const showIcon = w >= 80 && h >= 44;
      if (showIcon) {
        const iconUrl = getIconUrl(entry.raw);
        if (iconUrl) {
          const icon = document.createElement("img");
          icon.className = "item-icon";
          icon.src = iconUrl;
          icon.alt = "";
          icon.loading = "lazy";
          icon.decoding = "async";
          icon.onerror = () => { icon.style.display = "none"; };
          label.appendChild(icon);
        }
      }
      const text = document.createElement("span");
      text.textContent = displayName;
      label.appendChild(text);
      el.appendChild(label);
    }

    frag.appendChild(el);
  }
  container.appendChild(frag);
}

/**
 * @param {UiTopFlat} flat
 */
export function renderHeatmap(flat) {
  const canvas = /** @type {HTMLElement | null} */ (document.getElementById("heatmapCanvas"));
  const empty = /** @type {HTMLElement | null} */ (document.getElementById("heatmapEmpty"));
  if (!canvas || !empty) return;

  const baseList = flat?.[state.kind] || [];
  const entries = baseList.map(coerceEntry).filter((entry) => entry);
  const list = selectHeatmapEntries(/** @type {UiHeatmapEntry[]} */ (entries));

  canvas.innerHTML = "";
  if (list.length === 0) {
    empty.style.display = "block";
    return;
  }
  empty.style.display = "none";

  const utils = window.ScaleUtils;
  const amountValues = list.map(entry => entry.amount);
  const deltaValues = list.map(entry => entry.delta);
  const amountNorm = (utils && typeof utils.buildNormalizer === "function")
    ? utils.buildNormalizer(amountValues, "log1p")
    : () => 0;
  let deltaNorm = () => 0;
  if (utils && typeof utils.buildDeltaNormalizer === "function") {
    const normer = utils.buildDeltaNormalizer(deltaValues, "p95");
    if (normer && typeof normer.norm === "function") deltaNorm = normer.norm;
  }

  const normalized = list.map(entry => ({
    ...entry,
    deltaScaled: toNumber(deltaNorm(entry.delta), 0),
  }));

  const weighted = normalized.map(entry => ({
    item: entry,
    weight: Math.max(HEATMAP_EPS, toNumber(amountNorm(entry.amount), 0)),
  }));

  const rect = canvas.getBoundingClientRect();
  const width = rect.width || canvas.clientWidth;
  const height = rect.height || canvas.clientHeight;
  if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) {
    empty.style.display = "block";
    return;
  }

  const tiles = buildTreemap(weighted, width, height);
  const unit = unitFor(state.kind);
  renderTiles(canvas, tiles, unit, state.kind);
}
