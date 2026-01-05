// @ts-check

import { getDisplayName, normalizeResourceId } from "./i18n.js";
import { getIconUrl } from "./icons.js";
import { fmtRaw, formatValue, prettyName, unitFor } from "./format.js";
import { renderHeatmap } from "./heatmap.js";
import { applyMinRatio01, buildListNormalizer, toPerMinute } from "./scale_bridge.js";
import { KINDS, kindToKey } from "./kind.js";
import { BAR_MIN_RATIO, DELTA_UNIT, state } from "./state.js";

/** @typedef {import("./types.js").EntryUi} EntryUi */
/** @typedef {import("./types.js").DashboardData} DashboardData */
/** @typedef {import("./types.js").Kind} Kind */
/** @typedef {import("./types.js").TopMetric} TopMetric */
/** @typedef {import("./types.js").UiTopFlat} UiTopFlat */
/** @typedef {import("./types.js").UiTopFlatEntry} UiTopFlatEntry */

/**
 * @param {EntryUi[]} list
 * @param {TopMetric} valueKey
 * @param {string} metricClass
 * @param {string} arrow
 * @param {boolean} isRate
 * @param {"log1p"|"sqrt"} compressMethod
 * @returns {string}
 */
function tableFor(list, valueKey, metricClass, arrow, isRate, compressMethod) {
  if (!Array.isArray(list) || list.length === 0) return `<div class="muted">（データなし）</div>`;

  const baseValues = list.map(x => (x && typeof x[valueKey] === "number") ? x[valueKey] : 0);
  // NOTE: /hour toggle removed; keep /min fixed to avoid DOM dependency.
  const displayValues = baseValues;
  const method = compressMethod === "sqrt" ? "sqrt" : "log1p";
  const normalizer = buildListNormalizer(baseValues, method);
  const unit = unitFor(state.kind);

  const rows = list.map((x, i) => {
    const raw = (x.raw_name || x.id || x.display_name || x.name || "-");
    const info = normalizeResourceId(raw);
    const displayName = getDisplayName(raw);
    const badge = info.kind === "gas" ? "Gas" : (info.kind === "fluid" ? "Fluid" : "");
    const nameHtml = displayName === raw ? prettyName(raw) : displayName;
    const badgeHtml = badge ? ` <span class="kind-badge">${badge}</span>` : "";
    const iconUrl = getIconUrl(raw);
    const iconHtml = iconUrl ? `<img class="item-icon" src="${iconUrl}" alt="" loading="lazy" decoding="async" onerror="this.style.display='none'">` : "";
    const baseVal = baseValues[i] ?? 0;
    const v = displayValues[i] ?? 0;
    const n01 = normalizer(baseVal);
    const pct01 = baseVal > 0 ? applyMinRatio01(n01, BAR_MIN_RATIO) : 0;
    const pct = Math.max(0, Math.min(100, pct01 * 100));
    const display = formatValue(v);
    const rawTitle = fmtRaw(v);
    const arrowSpan = arrow ? `<span class="arrow">${arrow}</span>` : "";
    return `
      <tr>
        <td class="name" title="${raw}">${iconHtml}<span class="label">${nameHtml}</span>${badgeHtml}</td>
        <td>
          <div class="row">
            <div class="barwrap" style="flex:1;">
              <div class="bar ${metricClass}" style="width:${pct}%;"></div>
            </div>
            <div class="val" title="${rawTitle}">${arrowSpan}${display} <span class="unit">${unit}</span></div>
          </div>
        </td>
      </tr>
    `;
  }).join("");

  const perLabel = isRate ? "/min" : "";
  return `
    <table>
      <thead><tr><th>name</th><th style="width:70%;">value ${perLabel}</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

/**
 * @param {DashboardData} data
 * @param {TopMetric} metric
 * @param {Kind} kind
 * @returns {EntryUi[]}
 */
function topList(data, metric, kind) {
  const kindKey = kindToKey(kind);
  return (data.top?.[metric]?.[kindKey]) || [];
}

export function updateKindToggle() {
  document.querySelectorAll("#kindToggle .seg-btn").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.kind === state.kind);
  });
}

export function updateUnitLabels() {
  const unit = unitFor(state.kind);
  /** @type {HTMLElement} */ (document.getElementById("unit-amount")).textContent = unit;
  /** @type {HTMLElement} */ (document.getElementById("unit-growth")).textContent = unit;
  /** @type {HTMLElement} */ (document.getElementById("unit-decrease")).textContent = unit;
}

/**
 * @param {DashboardData} data
 */
export function renderMeta(data) {
  const meta = /** @type {HTMLElement} */ (document.getElementById("meta"));
  const source = data.source ?? "-";
  const ts = typeof data.ts === "number" ? data.ts : null;
  const now = Date.now() / 1000;
  const age = ts ? Math.max(0, Math.floor(now - ts)) : null;
  const time = ts ? new Date(ts * 1000).toLocaleString() : "-";
  const ageText = age !== null ? `${age}s ago` : "-";
  meta.textContent = age !== null ? `updated ${ageText}` : "updated -";
  meta.title = `source=${source}  ts=${time}`;
}

/**
 * @param {DashboardData} data
 * @returns {UiTopFlat}
 */
export function flattenTop(data) {
  const kinds = KINDS;
  const out = { item: [], fluid: [], gas: [] };
  const metrics = [
    { key: "amount", field: "amount" },
    { key: "growth", field: "growth" },
    { key: "decrease", field: "decrease" },
  ];

  for (const kind of kinds) {
    const map = new Map();
    for (const m of metrics) {
      const list = topList(data, m.key, kind);
      for (const entry of list) {
        if (!entry) continue;
        const id = entry.raw_name || entry.display_name || entry.id || entry.name || "-";
        if (!map.has(id)) {
          map.set(id, {
            raw_name: entry.raw_name || entry.id || "-",
            display_name: entry.display_name || entry.name || entry.raw_name || entry.id || "-",
            amount: 0,
            growth: 0,
            decrease: 0,
          });
        }
        const target = map.get(id);
        const val = typeof entry[m.key] === "number" ? entry[m.key] : 0;
        target[m.field] = val;
      }
    }
    out[kind] = Array.from(map.values()).map(x => ({
      ...x,
      net: (x.growth || 0) - (x.decrease || 0),
    }));
  }

  return out;
}

/**
 * @param {UiTopFlat} flat
 * @returns {{ item: unknown, fluid: unknown, gas: unknown } | null}
 */
export function buildDeltaNormalizersByKind(flat) {
  const utils = window.ScaleUtils;
  if (!utils || typeof utils.buildDeltaNormalizer !== "function") return null;
  const out = { item: null, fluid: null, gas: null };
  const opts = { kStrategy: "p95", percentile: 0.95 };
  for (const kind of Object.keys(out)) {
    const deltas = flat[kind].map(x => {
      const growth = typeof x.growth === "number" ? x.growth : 0;
      const decrease = typeof x.decrease === "number" ? x.decrease : 0;
      return toPerMinute(growth - decrease, DELTA_UNIT);
    });
    out[kind] = utils.buildDeltaNormalizer(deltas, opts);
  }
  return out;
}

/**
 * @param {DashboardData} data
 */
export function renderTable(data) {
  if (!data) return;
  updateUnitLabels();
  const amount = topList(data, "amount", state.kind);
  const growth = topList(data, "growth", state.kind);
  const decrease = topList(data, "decrease", state.kind);

  /** @type {HTMLElement} */ (document.getElementById("amount")).innerHTML = tableFor(amount, "amount", "amount", "", false, "log1p");
  /** @type {HTMLElement} */ (document.getElementById("growth")).innerHTML = tableFor(growth, "growth", "growth", "↑", true, "log1p");
  /** @type {HTMLElement} */ (document.getElementById("decrease")).innerHTML = tableFor(decrease, "decrease", "decrease", "↓", true, "log1p");
}

/**
 * @param {DashboardData} data
 */
export function renderHeatmapView(data) {
  if (!data) return;
  const flat = flattenTop(data);
  state.lastDeltaNormalizers = buildDeltaNormalizersByKind(flat);
  renderHeatmap(flat);
}
