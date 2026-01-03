// @ts-check

import { getDisplayName, normalizeResourceId } from "./i18n.js";
import { getIconUrl } from "./icons.js";
import { fmtRaw, formatValue, prettyName, scaleValue, unitFor } from "./format.js";
import { renderHeatmap } from "./heatmap.js";
import { applyMinRatio01, buildListNormalizer, toPerMinute } from "./scale_bridge.js";
import { BAR_MIN_RATIO, DELTA_UNIT, kindLabel, state } from "./state.js";

/** @typedef {import("./types.js").TopEntry} TopEntry */
/** @typedef {import("./types.js").DashboardData} DashboardData */

/**
 * @param {TopEntry[]} list
 * @param {string} valueKey
 * @param {string} metricClass
 * @param {string} arrow
 * @param {boolean} isRate
 * @param {"log1p"|"sqrt"} compressMethod
 * @returns {string}
 */
function tableFor(list, valueKey, metricClass, arrow, isRate, compressMethod) {
  if (!Array.isArray(list) || list.length === 0) return `<div class="muted">（データなし）</div>`;

  const perHourEl = /** @type {HTMLInputElement | null} */ (document.getElementById("perHour"));
  const perHour = perHourEl?.checked;
  const displayScale = isRate && perHour ? 60 : 1;

  const baseValues = list.map(x => (x && typeof x[valueKey] === "number") ? x[valueKey] : 0);
  const displayValues = baseValues.map(v => v * displayScale);
  const method = compressMethod === "sqrt" ? "sqrt" : "log1p";
  const normalizer = buildListNormalizer(baseValues, method);
  const unit = unitFor(state.kind);

  const rows = list.map((x, i) => {
    const raw = (x.raw_name || x.display_name || "-");
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

  const perLabel = isRate ? (perHour ? "/hour" : "/min") : "";
  return `
    <table>
      <thead><tr><th>name</th><th style="width:70%;">value ${perLabel}</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

/**
 * @param {DashboardData} data
 * @param {string} metric
 * @param {string} kind
 * @returns {TopEntry[]}
 */
function topList(data, metric, kind) {
  return (data.top?.[metric]?.[kind]) || [];
}

/**
 * @param {TopEntry[]} list
 * @param {string} valueKey
 * @returns {{ name: string, value: number } | null}
 */
function topOne(list, valueKey) {
  if (!Array.isArray(list) || list.length === 0) return null;
  const entry = list[0];
  if (!entry) return null;
  const name = entry.display_name || entry.raw_name || "-";
  const v = typeof entry[valueKey] === "number" ? entry[valueKey] : 0;
  return { name, value: v };
}

/**
 * @param {DashboardData} data
 * @param {(kind: import("./state.js").Kind) => void} [onKindSelect]
 */
export function renderSummary(data, onKindSelect) {
  const summary = /** @type {HTMLElement} */ (document.getElementById("summary"));
  const kinds = ["item", "fluid", "gas"];

  const cards = kinds.map(kind => {
    const amountTop = topOne(topList(data, "amount", kind), "amount");
    const growthTop = topOne(topList(data, "growth_per_min", kind), "growth_per_min");
    const decreaseTop = topOne(topList(data, "decrease_per_min", kind), "decrease_per_min");

    const amountValue = amountTop ? formatValue(amountTop.value) : "-";
    const growthValue = growthTop ? formatValue(scaleValue(growthTop.value)) : "-";
    const decreaseValue = decreaseTop ? formatValue(scaleValue(decreaseTop.value)) : "-";
    const amountTitle = amountTop ? fmtRaw(amountTop.value) : "-";
    const growthTitle = growthTop ? fmtRaw(scaleValue(growthTop.value)) : "-";
    const decreaseTitle = decreaseTop ? fmtRaw(scaleValue(decreaseTop.value)) : "-";
    const unit = unitFor(kind);

    const isActive = state.kind === kind ? "active" : "";
    return `
      <div class="card summary-card ${isActive}" data-kind="${kind}">
        <div class="summary-row">
          <div>
            <div class="summary-kind">${kindLabel[kind]}</div>
            <div class="summary-metric">Amount <span class="unit">${unitFor(kind)}</span></div>
          </div>
          <div class="val" title="${amountTitle}">${amountValue} <span class="unit">${unit}</span></div>
        </div>
        <div class="summary-row">
          <div class="summary-metric">↑ Growth</div>
          <div class="val" title="${growthTitle}"><span class="arrow">↑</span>${growthValue} <span class="unit">${unit}</span></div>
        </div>
        <div class="summary-row">
          <div class="summary-metric">↓ Decrease</div>
          <div class="val" title="${decreaseTitle}"><span class="arrow">↓</span>${decreaseValue} <span class="unit">${unit}</span></div>
        </div>
      </div>
    `;
  }).join("");

  summary.innerHTML = cards;
  if (onKindSelect) {
    summary.querySelectorAll(".summary-card").forEach(card => {
      card.addEventListener("click", () => {
        const kind = /** @type {import("./state.js").Kind} */ (card.dataset.kind);
        if (!kind) return;
        onKindSelect(kind);
      });
    });
  }
}

export function updateTabs() {
  document.querySelectorAll(".tab").forEach(b => {
    b.classList.toggle("active", b.dataset.kind === state.kind);
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
 * @returns {{ item: Array<{ raw_name: string, display_name: string, amount: number, growth: number, decrease: number, net: number }>, fluid: Array<{ raw_name: string, display_name: string, amount: number, growth: number, decrease: number, net: number }>, gas: Array<{ raw_name: string, display_name: string, amount: number, growth: number, decrease: number, net: number }> }}
 */
export function flattenTop(data) {
  const kinds = ["item", "fluid", "gas"];
  const out = { item: [], fluid: [], gas: [] };
  const metrics = [
    { key: "amount", field: "amount" },
    { key: "growth_per_min", field: "growth" },
    { key: "decrease_per_min", field: "decrease" },
  ];

  for (const kind of kinds) {
    const map = new Map();
    for (const m of metrics) {
      const list = topList(data, m.key, kind);
      for (const entry of list) {
        if (!entry) continue;
        const id = entry.raw_name || entry.display_name || "-";
        if (!map.has(id)) {
          map.set(id, {
            raw_name: entry.raw_name || "-",
            display_name: entry.display_name || entry.raw_name || "-",
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
 * @param {{ item: Array<{ growth: number, decrease: number }>, fluid: Array<{ growth: number, decrease: number }>, gas: Array<{ growth: number, decrease: number }> }} flat
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
 * @param {{ onKindSelect?: (kind: import("./state.js").Kind) => void }} [opts]
 */
export function render(data, opts = {}) {
  if (!data) return;
  renderMeta(data);
  renderSummary(data, opts.onKindSelect);
  updateUnitLabels();
  const flat = flattenTop(data);
  state.lastDeltaNormalizers = buildDeltaNormalizersByKind(flat);

  if (state.view === "list") {
    const amount = topList(data, "amount", state.kind);
    const growth = topList(data, "growth_per_min", state.kind);
    const decrease = topList(data, "decrease_per_min", state.kind);

    /** @type {HTMLElement} */ (document.getElementById("amount")).innerHTML = tableFor(amount, "amount", "amount", "", false, "log1p");
    /** @type {HTMLElement} */ (document.getElementById("growth")).innerHTML = tableFor(growth, "growth_per_min", "growth", "↑", true, "log1p");
    /** @type {HTMLElement} */ (document.getElementById("decrease")).innerHTML = tableFor(decrease, "decrease_per_min", "decrease", "↓", true, "log1p");
    return;
  }

  renderHeatmap(flat);
}
