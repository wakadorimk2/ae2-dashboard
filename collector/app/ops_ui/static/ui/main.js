// @ts-check

import { loadDisplayNameDict } from "./i18n.js";
import { loadIconIndex } from "./icons.js";
import { render, updateTabs } from "./render.js";
import { state } from "./state.js";

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
 * @param {import("./state.js").Kind} kind
 */
function onKindSelect(kind) {
  state.activeKind = kind;
  updateTabs();
  load();
}

/**
 * @param {unknown} data
 */
function renderWithHandlers(data) {
  if (!data) return;
  render(/** @type {import("./types.js").DashboardData} */ (data), { onKindSelect });
}

export async function load() {
  setErr("");
  const topnEl = /** @type {HTMLInputElement} */ (document.getElementById("topn"));
  const topn = topnEl.value;
  const url = `/dashboard?top_n=${encodeURIComponent(topn)}`;
  let data;
  try {
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) {
      const t = await res.text();
      throw new Error(`HTTP ${res.status}: ${t}`);
    }
    data = await res.json();
  } catch (e) {
    setErr(String(e));
    return;
  }

  state.lastData = data;
  renderWithHandlers(data);
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

/**
 * @param {import("./state.js").ViewMode} mode
 */
export function setView(mode) {
  state.viewMode = mode;
  document.querySelectorAll("#viewToggle .seg-btn").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.view === state.viewMode);
  });
  /** @type {HTMLElement} */ (document.getElementById("viewList")).style.display = state.viewMode === "list" ? "block" : "none";
  /** @type {HTMLElement} */ (document.getElementById("viewHeatmap")).style.display = state.viewMode === "heatmap" ? "block" : "none";
  renderWithHandlers(state.lastData);
}

/**
 * @param {import("./state.js").FormatMode} mode
 */
export function setFormat(mode) {
  state.formatMode = mode;
  document.querySelectorAll("#formatToggle .seg-btn").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.format === state.formatMode);
  });
  renderWithHandlers(state.lastData);
}

function updateHeatmapToggles() {
  document.querySelectorAll("#heatmapCountToggle .seg-btn").forEach(btn => {
    const count = Number(btn.dataset.count);
    btn.classList.toggle("active", count === state.heatmapCount);
  });
  document.querySelectorAll("#heatmapSortToggle .seg-btn").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.sort === state.heatmapSort);
  });
}

document.getElementById("topn").addEventListener("input", (e) => {
  const target = /** @type {HTMLInputElement} */ (e.target);
  /** @type {HTMLElement} */ (document.getElementById("topnVal")).textContent = target.value;
});

document.querySelectorAll(".tab").forEach(btn => {
  btn.addEventListener("click", () => {
    const kind = /** @type {import("./state.js").Kind} */ (btn.dataset.kind);
    if (!kind) return;
    state.activeKind = kind;
    updateTabs();
    load();
  });
});

document.getElementById("perHour").addEventListener("change", () => {
  renderWithHandlers(state.lastData);
});

document.querySelectorAll("#viewToggle .seg-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    const mode = /** @type {import("./state.js").ViewMode} */ (btn.dataset.view);
    if (!mode) return;
    setView(mode);
  });
});

document.querySelectorAll("#formatToggle .seg-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    const mode = /** @type {import("./state.js").FormatMode} */ (btn.dataset.format);
    if (!mode) return;
    setFormat(mode);
  });
});

document.querySelectorAll("#heatmapCountToggle .seg-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    const count = Number(btn.dataset.count);
    if (!Number.isFinite(count) || !count) return;
    state.heatmapCount = count;
    updateHeatmapToggles();
    renderWithHandlers(state.lastData);
  });
});

document.querySelectorAll("#heatmapSortToggle .seg-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    const sort = /** @type {import("./state.js").HeatmapSort} */ (btn.dataset.sort);
    if (!sort) return;
    state.heatmapSort = sort;
    updateHeatmapToggles();
    renderWithHandlers(state.lastData);
  });
});

setView("list");
setFormat("compact");
updateHeatmapToggles();
loadDisplayNameDict().then(() => {
  if (state.lastData) renderWithHandlers(state.lastData);
});
loadIconIndex().then(() => {
  if (state.lastData) renderWithHandlers(state.lastData);
});
load();
setAuto(true);
