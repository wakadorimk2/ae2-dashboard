// @ts-check

import "./scale.js";
import "./styles.css";
import { loadDisplayNameDict } from "./i18n.js";
import { loadIconIndex } from "./icons.js";
import { normalizeDashboardData } from "./normalize.js";
import { renderHeatmapView, renderMeta, renderTable, updateKindToggle } from "./render.js";
import { state, TOP_N } from "./state.js";

/**
 * @param {string} msg
 */
function setErr(msg) {
  const el = /** @type {HTMLElement} */ (document.getElementById("err"));
  if (!msg) {
    el.style.display = "none";
    el.textContent = "";
    return;
  }
  el.style.display = "block";
  el.textContent = msg;
}

/**
 * @typedef {"heatmap" | "list"} ViewMode
 */

const VIEW_HEATMAP = "heatmap";
const VIEW_LIST = "list";

/**
 * @returns {ViewMode}
 */
function getViewFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const viewParam = params.get("view");
  if (viewParam === VIEW_LIST) return VIEW_LIST;
  if (viewParam === VIEW_HEATMAP) return VIEW_HEATMAP;
  const hash = window.location.hash.replace("#", "");
  if (hash === VIEW_LIST || hash === VIEW_HEATMAP) return /** @type {ViewMode} */ (hash);
  return VIEW_HEATMAP;
}

/**
 * @param {ViewMode} view
 */
function updateViewToggle(view) {
  document.querySelectorAll("#viewToggle .seg-btn").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.view === view);
  });
}

/**
 * @param {ViewMode} view
 */
function applyView(view) {
  const heatmap = /** @type {HTMLElement | null} */ (document.getElementById("viewHeatmap"));
  const list = /** @type {HTMLElement | null} */ (document.getElementById("viewList"));
  const isHeatmap = view === VIEW_HEATMAP;
  if (heatmap) heatmap.classList.toggle("is-hidden", !isHeatmap);
  if (list) list.classList.toggle("is-hidden", isHeatmap);
  updateViewToggle(view);
}

let currentView = getViewFromUrl();

/**
 * @param {import("./types.js").DashboardData | undefined} data
 */
function renderForView(data) {
  if (!data) return;
  renderMeta(data);
  if (currentView === VIEW_LIST) {
    renderTable(data);
  } else {
    renderHeatmapView(data);
  }
}

/**
 * @param {import("./types.js").Kind} kind
 */
function onKindSelect(kind) {
  state.kind = kind;
  updateKindToggle();
  if (state.lastData) {
    renderForView(state.lastData);
    return;
  }
  load();
}

/**
 * @param {ViewMode} nextView
 */
function setView(nextView) {
  if (nextView === currentView) return;
  currentView = nextView;
  applyView(currentView);
  if (state.lastData) renderForView(state.lastData);
}

export async function load() {
  setErr("");
  const url = `/dashboard?top_n=${encodeURIComponent(String(TOP_N))}`;
  let data;
  try {
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) {
      const t = await res.text();
      throw new Error(`HTTP ${res.status}: ${t}`);
    }
    data = normalizeDashboardData(await res.json());
  } catch (e) {
    setErr(String(e));
    return;
  }

  state.lastData = data;
  renderForView(data);
}

/**
 * @param {boolean} on
 */
export function setAuto(on) {
  if (state.timer) {
    clearInterval(state.timer);
    state.timer = null;
  }
  if (on) state.timer = setInterval(load, 10000);
}

document.querySelectorAll("#kindToggle .seg-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    const kind = /** @type {import("./types.js").Kind} */ (btn.dataset.kind);
    if (!kind) return;
    if (kind === state.kind) return;
    onKindSelect(kind);
  });
});

updateKindToggle();
applyView(currentView);
window.addEventListener("hashchange", () => setView(getViewFromUrl()));
window.addEventListener("popstate", () => setView(getViewFromUrl()));

// 先に1回だけデータを取る
load();

// 後から辞書/アイコンが来たら、あれば再描画
loadDisplayNameDict().then(() => {
  if (state.lastData) renderForView(state.lastData);
});
loadIconIndex().then(() => {
  if (state.lastData) renderForView(state.lastData);
});

// 自動更新スタート
setAuto(true);
