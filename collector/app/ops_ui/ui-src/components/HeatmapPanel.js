// @ts-check

import { unitFor } from "../format.js";
import { state } from "../state.js";
import { buildTreemap } from "./heatmap_layout.js";
import { coerceEntry, OTHERS_RAW, selectHeatmapEntries, toNumber } from "./heatmap_model.js";
import { renderTiles } from "./heatmap_render.js";

/** @typedef {import("../types.js").Kind} Kind */
/** @typedef {import("../types.js").UiTopFlat} UiTopFlat */
/** @typedef {import("../types.js").UiHeatmapEntry} UiHeatmapEntry */

/**
 * @typedef {Object} HeatmapPanelProps
 * @property {string} [title]
 * @property {HTMLElement | null} canvasEl
 * @property {HTMLElement | null} emptyEl
 * @property {HTMLElement | null} [titleEl]
 * @property {Kind} [kind]
 * @property {UiTopFlat} data
 * @property {(entry: UiHeatmapEntry, event: MouseEvent | KeyboardEvent) => void} [onTileClick]
 */

const HEATMAP_EPS = 0.02;

/**
 * @returns {boolean}
 */
function shouldLogHeatmapDebug() {
  return Boolean((/** @type {any} */ (window)).DEBUG_HEATMAP);
}

/**
 * @param {HeatmapPanelProps} props
 */
export function HeatmapPanel(props) {
  if (!props || !props.data) return;
  const { title, kind, data, onTileClick, canvasEl, emptyEl, titleEl } = props;
  if (!canvasEl || !emptyEl) return;

  if (typeof title === "string" && titleEl) {
    titleEl.textContent = title;
  }

  const VALID_KINDS = new Set(["item", "fluid", "gas"]);

  const resolveKind = kind ?? state.kind;
  const activeKind = VALID_KINDS.has(resolveKind) ? resolveKind : "item";
  const baseList = data?.[activeKind] || [];
  const entries = baseList.map(coerceEntry).filter((entry) => entry);
  const list = selectHeatmapEntries(/** @type {UiHeatmapEntry[]} */ (entries));
  if (shouldLogHeatmapDebug()) {
    const others = list.find(entry => entry.raw === OTHERS_RAW);
    const tail = list.slice(-3).map(entry => entry.name || "-");
    console.log(
      `[heatmap] raw=${entries.length} selected=${list.length} others=${others ? "yes" : "no"} tail=${tail.join(", ")}`
    );
  }

  canvasEl.innerHTML = "";
  if (list.length === 0) {
    emptyEl.style.display = "block";
    return;
  }
  emptyEl.style.display = "none";

  const utils = window.ScaleUtils;
  // ScaleUtils is expected to be loaded via scale.js before HeatmapPanel renders.
  if (!utils && shouldLogHeatmapDebug()) {
    console.debug("[heatmap] ScaleUtils not found: normalization disabled");
  }
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

  const rect = canvasEl.getBoundingClientRect();
  const width = rect.width || canvasEl.clientWidth;
  const height = rect.height || canvasEl.clientHeight;
  if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) {
    emptyEl.style.display = "block";
    return;
  }

  const tiles = buildTreemap(weighted, width, height);
  const unit = unitFor(activeKind);
  renderTiles(canvasEl, tiles, unit, activeKind, onTileClick);
}
