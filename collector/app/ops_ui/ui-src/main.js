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
 * NOTE: Internal values remain "heatmap"/"list" for URL compatibility.
 * UI labels are now "Observe"/"Inspect" to reflect user experience flow.
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
/** @type {ResizeObserver | null} */
let heatmapResizeObserver = null;

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

function setupHeatmapResizeObserver() {
  const canvas = /** @type {HTMLElement | null} */ (document.getElementById("heatmapCanvas"));
  if (!canvas || typeof ResizeObserver !== "function") return;
  if (heatmapResizeObserver) return;

  let lastW = 0;
  let lastH = 0;
  /** @type {number | null} */
  let resizeTimer = null;

  const observer = new ResizeObserver(entries => {
    const entry = entries[0];
    if (!entry) return;
    const rect = entry.contentRect;
    const w = Math.round(rect.width);
    const h = Math.round(rect.height);
    if (w <= 0 || h <= 0) return;
    if (w === lastW && h === lastH) return;
    lastW = w;
    lastH = h;
    if (resizeTimer) return;
    resizeTimer = window.setTimeout(() => {
      resizeTimer = null;
      if (currentView !== VIEW_HEATMAP) return;
      if (state.lastData) renderHeatmapView(state.lastData);
    }, 100);
  });

  observer.observe(canvas);
  heatmapResizeObserver = observer;
}

/**
 * @returns {boolean}
 */
function getSnapshotFlag() {
  const params = new URLSearchParams(window.location.search);
  return params.get("snapshot") === "1";
}

/**
 * @returns {Promise<import("./types.js").DashboardData>}
 */
async function fetchDashboardData() {
  const url = `/dashboard?top_n=${encodeURIComponent(String(TOP_N))}`;
  const fetchFromApi = async () => {
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) {
      const t = await res.text();
      throw new Error(`HTTP ${res.status}: ${t}`);
    }
    return normalizeDashboardData(await res.json());
  };

  if (!getSnapshotFlag()) return fetchFromApi();

  const resolveSnapshotUrl = async () => {
    const baseFromEnv = import.meta.env.BASE_URL;
    if (baseFromEnv) {
      try {
        const envBaseUrl = new URL(baseFromEnv, window.location.href).toString();
        return new URL("fixtures/snapshot.json", envBaseUrl).toString();
      } catch {
        // fall through
      }
    }

    try {
      const manifestUrl = new URL("manifest.json", window.location.href).toString();
      const res = await fetch(manifestUrl, { cache: "no-store" });
      if (res.ok) {
        const manifestDirUrl = new URL("./", res.url).toString();
        return new URL("fixtures/snapshot.json", manifestDirUrl).toString();
      }
    } catch {
      // fall through
    }

    const pageDirUrl = new URL("./", window.location.href).toString();
    return new URL("fixtures/snapshot.json", pageDirUrl).toString();
  };

  const snapshotUrl = await resolveSnapshotUrl();
  try {
    const res = await fetch(snapshotUrl, { cache: "no-store" });
    if (!res.ok) {
      const t = await res.text();
      throw new Error(`HTTP ${res.status}: ${t}`);
    }
    return normalizeDashboardData(await res.json());
  } catch (e) {
    console.warn(`snapshot fetch failed; fallback to API (expected at ${snapshotUrl})`, e);
    return fetchFromApi();
  }
}

export async function load() {
  setErr("");
  let data;
  try {
    data = await fetchDashboardData();
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
setupHeatmapResizeObserver();
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
