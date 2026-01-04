// @ts-check

import "./scale.js";
import "./styles.css";
import { loadDisplayNameDict } from "./i18n.js";
import { loadIconIndex } from "./icons.js";
import { normalizeDashboardData } from "./normalize.js";
import { render, updateKindToggle } from "./render.js";
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
 * @param {import("./types.ts").Kind} kind
 */
function onKindSelect(kind) {
  state.kind = kind;
  updateKindToggle();
  if (state.lastData) {
    renderWithHandlers(state.lastData);
    return;
  }
  load();
}

/**
 * @param {import("./types.ts").DashboardData | undefined} data
 */
function renderWithHandlers(data) {
  if (!data) return;
  render(data);
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

document.querySelectorAll("#kindToggle .seg-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    const kind = /** @type {import("./types.ts").Kind} */ (btn.dataset.kind);
    if (!kind) return;
    if (kind === state.kind) return;
    onKindSelect(kind);
  });
});

updateKindToggle();
loadDisplayNameDict().then(() => {
  if (state.lastData) renderWithHandlers(state.lastData);
});
loadIconIndex().then(() => {
  if (state.lastData) renderWithHandlers(state.lastData);
});
load();
setAuto(true);
