let activeKind = "item";
let viewMode = "list";
let formatMode = "compact";
let lastData = null;
let timer = null;

const kindLabel = {
  item: "Items",
  fluid: "Fluids",
  gas: "Gases",
};

const kindUnit = {
  item: "items",
  fluid: "mB",
  gas: "mB",
};

let displayNameDict = {};
let displayNameLang = "ja";

function normalizeResourceId(id){
  if (typeof id !== "string") return { normalized: id, kind: undefined };
  const parts = id.split(":");
  if (parts.length >= 3 && (parts[0] === "fluid" || parts[0] === "gas")){
    return { normalized: parts.slice(1).join(":"), kind: parts[0] };
  }
  return { normalized: id, kind: undefined };
}

function resolveDisplayNameLang(){
  const param = new URLSearchParams(window.location.search).get("lang");
  if (param === "ja" || param === "en" || param === "both") return param;
  return "ja";
}

async function loadDisplayNameDict(){
  displayNameLang = resolveDisplayNameLang();
  try{
    const res = await fetch("/dashboard/ui/static/i18n/display_names.json", { cache: "no-store" });
    if (!res.ok) return;
    const data = await res.json();
    if (data && typeof data === "object") displayNameDict = data;
  }catch(_e){
    // Optional file; ignore load errors.
  }
}

function autoDisplayNameFromId(id){
  if (typeof id !== "string") return "";
  const base = id.includes(":") ? id.split(":")[1] : id;
  const spaced = base.replace(/[_\.-]+/g, " ").replace(/\s+/g, " ").trim();
  if (!spaced) return "";
  return spaced
    .split(" ")
    .map(w => w ? w[0].toUpperCase() + w.slice(1).toLowerCase() : "")
    .join(" ");
}

function getDisplayName(id, lang){
  if (typeof id !== "string" || !id) return "-";
  const info = normalizeResourceId(id);
  const normalized = typeof info.normalized === "string" ? info.normalized : id;
  const entry = displayNameDict[normalized];
  const preferred = lang || displayNameLang || "ja";
  if (entry && typeof entry === "object"){
    const ja = typeof entry.ja === "string" ? entry.ja : "";
    const en = typeof entry.en === "string" ? entry.en : "";
    if (preferred === "both"){
      if (ja && en) return `${ja} (${en})`;
      if (ja) return ja;
      if (en) return en;
    }else if (preferred === "en"){
      if (en) return en;
      if (ja) return ja;
    }else{
      if (ja) return ja;
      if (en) return en;
    }
  }
  const auto = autoDisplayNameFromId(normalized);
  if (auto) return auto;
  return normalized || id;
}

function fmtRaw(n){
  if (n === null || n === undefined) return "-";
  if (typeof n !== "number" || Number.isNaN(n)) return String(n);
  return n.toLocaleString("en-US");
}

function trimZeros(str){
  return str.replace(/\.0+$/, "").replace(/(\.\d*[1-9])0+$/, "$1");
}

function compactDecimals(unit, val){
  if (unit === "K") return val >= 100 ? 0 : 1;
  if (val >= 100) return 0;
  if (val >= 10) return 1;
  return 2;
}

function fmtCompact(n){
  if (n === null || n === undefined) return "-";
  if (typeof n !== "number" || Number.isNaN(n)) return String(n);

  const sign = n < 0 ? "-" : "";
  const abs = Math.abs(n);
  const units = [
    { v: 1e12, s: "T" },
    { v: 1e9, s: "G" },
    { v: 1e6, s: "M" },
    { v: 1e3, s: "K" },
  ];
  for (const u of units){
    if (abs >= u.v){
      const val = abs / u.v;
      const decimals = compactDecimals(u.s, val);
      return `${sign}${trimZeros(val.toFixed(decimals))}${u.s}`;
    }
  }
  return `${sign}${fmtRaw(abs)}`;
}

function formatValue(n){
  return formatMode === "compact" ? fmtCompact(n) : fmtRaw(n);
}

function setErr(msg){
  const el = document.getElementById("err");
  if (!msg) { el.style.display="none"; el.textContent=""; return; }
  el.style.display="block"; el.textContent = msg;
}

function prettyName(name){
  const idx = name.indexOf(":");
  if (idx <= 0) return name;
  const ns = name.slice(0, idx+1);
  const rest = name.slice(idx+1);
  return `<span class="muted">${ns}</span>${rest}`;
}

function unitFor(kind){
  return kindUnit[kind] || "";
}

function scaleValue(n){
  if (typeof n !== "number") return 0;
  const perHour = document.getElementById("perHour")?.checked;
  const scale = perHour ? 60 : 1;
  return n * scale;
}

function tableFor(list, valueKey, metricClass, arrow, isRate){
  if (!Array.isArray(list) || list.length === 0) return `<div class="muted">（データなし）</div>`;

  const perHour = document.getElementById("perHour")?.checked;
  const scale = isRate && perHour ? 60 : 1;

  const values = list.map(x => (x && typeof x[valueKey] === "number") ? x[valueKey] * scale : 0);
  const max = Math.max(...values, 1);
  const unit = unitFor(activeKind);

  const rows = list.map((x, i) => {
    const raw = (x.raw_name || x.display_name || "-");
    const info = normalizeResourceId(raw);
    const displayName = getDisplayName(raw);
    const badge = info.kind === "gas" ? "Gas" : (info.kind === "fluid" ? "Fluid" : "");
    const nameHtml = displayName === raw ? prettyName(raw) : displayName;
    const badgeHtml = badge ? ` <span class="kind-badge">${badge}</span>` : "";
    const v = values[i] ?? 0;
    const pct = Math.max(0, Math.min(100, (v / max) * 100));
    const display = formatValue(v);
    const rawTitle = fmtRaw(v);
    const arrowSpan = arrow ? `<span class="arrow">${arrow}</span>` : "";
    return `
      <tr>
        <td class="name" title="${raw}"><span class="label">${nameHtml}</span>${badgeHtml}</td>
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

function topList(data, metric, kind){
  return (data.top?.[metric]?.[kind]) || [];
}

function topOne(list, valueKey){
  if (!Array.isArray(list) || list.length === 0) return null;
  const entry = list[0];
  if (!entry) return null;
  const name = entry.display_name || entry.raw_name || "-";
  const v = typeof entry[valueKey] === "number" ? entry[valueKey] : 0;
  return { name, value: v };
}

function renderSummary(data){
  const summary = document.getElementById("summary");
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

    const isActive = activeKind === kind ? "active" : "";
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
  summary.querySelectorAll(".summary-card").forEach(card => {
    card.addEventListener("click", () => {
      activeKind = card.dataset.kind;
      updateTabs();
      load();
    });
  });
}

function updateTabs(){
  document.querySelectorAll(".tab").forEach(b => {
    b.classList.toggle("active", b.dataset.kind === activeKind);
  });
}

function updateUnitLabels(){
  const unit = unitFor(activeKind);
  document.getElementById("unit-amount").textContent = unit;
  document.getElementById("unit-growth").textContent = unit;
  document.getElementById("unit-decrease").textContent = unit;
}

function renderMeta(data){
  const meta = document.getElementById("meta");
  const source = data.source ?? "-";
  const ts = typeof data.ts === "number" ? data.ts : null;
  const now = Date.now() / 1000;
  const age = ts ? Math.max(0, Math.floor(now - ts)) : null;
  const time = ts ? new Date(ts * 1000).toLocaleString() : "-";
  const ageText = age !== null ? `${age}s ago` : "-";
  meta.textContent = age !== null ? `updated ${ageText}` : "updated -";
  meta.title = `source=${source}  ts=${time}`;
}

function flattenTop(data){
  const kinds = ["item", "fluid", "gas"];
  const out = { item: [], fluid: [], gas: [] };
  const metrics = [
    { key: "amount", field: "amount" },
    { key: "growth_per_min", field: "growth" },
    { key: "decrease_per_min", field: "decrease" },
  ];

  for (const kind of kinds){
    const map = new Map();
    for (const m of metrics){
      const list = topList(data, m.key, kind);
      for (const entry of list){
        if (!entry) continue;
        const id = entry.raw_name || entry.display_name || "-";
        if (!map.has(id)){
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

function renderHeatmap(data){
  const heatmap = document.getElementById("viewHeatmap");
  const flat = flattenTop(data);
  const total = Object.values(flat).reduce((acc, list) => acc + list.length, 0);
  heatmap.querySelector(".muted").textContent = `Coming soon. (${total} nodes prepared)`;
}

function render(data){
  if (!data) return;
  renderMeta(data);
  renderSummary(data);
  updateUnitLabels();

  const amount = topList(data, "amount", activeKind);
  const growth = topList(data, "growth_per_min", activeKind);
  const decrease = topList(data, "decrease_per_min", activeKind);

  document.getElementById("amount").innerHTML = tableFor(amount, "amount", "amount", "", false);
  document.getElementById("growth").innerHTML = tableFor(growth, "growth_per_min", "growth", "↑", true);
  document.getElementById("decrease").innerHTML = tableFor(decrease, "decrease_per_min", "decrease", "↓", true);

  renderHeatmap(data);
}

async function load(){
  setErr("");
  const topn = document.getElementById("topn").value;
  const url = `/dashboard?top_n=${encodeURIComponent(topn)}`;
  let data;
  try{
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok){
      const t = await res.text();
      throw new Error(`HTTP ${res.status}: ${t}`);
    }
    data = await res.json();
  }catch(e){
    setErr(String(e));
    return;
  }

  lastData = data;
  render(data);
}

function setAuto(on){
  if (timer) { clearInterval(timer); timer = null; }
  if (on) timer = setInterval(load, 10000);
}

function setView(mode){
  viewMode = mode;
  document.querySelectorAll("#viewToggle .seg-btn").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.view === viewMode);
  });
  document.getElementById("viewList").style.display = viewMode === "list" ? "block" : "none";
  document.getElementById("viewHeatmap").style.display = viewMode === "heatmap" ? "block" : "none";
}

function setFormat(mode){
  formatMode = mode;
  document.querySelectorAll("#formatToggle .seg-btn").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.format === formatMode);
  });
  render(lastData);
}

document.getElementById("topn").addEventListener("input", (e) => {
  document.getElementById("topnVal").textContent = e.target.value;
});

document.querySelectorAll(".tab").forEach(btn => {
  btn.addEventListener("click", () => {
    activeKind = btn.dataset.kind;
    updateTabs();
    load();
  });
});

document.getElementById("perHour").addEventListener("change", () => {
  render(lastData);
});

document.querySelectorAll("#viewToggle .seg-btn").forEach(btn => {
  btn.addEventListener("click", () => setView(btn.dataset.view));
});

document.querySelectorAll("#formatToggle .seg-btn").forEach(btn => {
  btn.addEventListener("click", () => setFormat(btn.dataset.format));
});

setView("list");
setFormat("compact");
loadDisplayNameDict().then(() => {
  if (lastData) render(lastData);
});
load();
setAuto(true);
