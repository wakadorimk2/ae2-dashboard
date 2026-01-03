from __future__ import annotations
import json, time
from typing import Any, Dict
from fastapi import APIRouter, HTTPException, Query
from . import settings
from .models import IngestPayload
from .storage_gcs import save_jsonl_to_gcs, save_json_to_gcs, load_json_from_gcs
from .summarize import summarize_items, compute_rankings

router = APIRouter()

def _latest_object_name() -> str:
    prefix = settings.GCS_PREFIX.strip("/")
    if prefix:
        return f"{prefix}/latest.json"
    return "latest.json"

@router.get("/")
def root() -> Dict[str, Any]:
    return {"ok": True, "name": settings.APP_NAME, "ts": time.time()}

@router.get("/health")
def health() -> Dict[str, Any]:
    return {"ok": True, "name": settings.APP_NAME, "ts": time.time()}

@router.post("/ingest")
def ingest(payload: IngestPayload) -> Dict[str, Any]:
    if len(payload.items) > settings.MAX_ITEMS:
        raise HTTPException(status_code=413, detail=f"too many items: {len(payload.items)} > {settings.MAX_ITEMS}")

    if settings.LOG_RAW:
        # 元のmain.pyの挙動と同じ :contentReference[oaicite:2]{index=2}
        print(json.dumps({"type": "raw_payload", **payload.model_dump()}, ensure_ascii=False))

    dump = payload.model_dump()
    gcs_path = save_jsonl_to_gcs(dump)

    ts = payload.ts or time.time()

    summary = summarize_items(payload.items)
    ranks = compute_rankings(payload.items, ts=ts, top_n=20, min_amount_for_top=0)
    resp = {
        "ok": True,
        "gcs_path": gcs_path,
        "ts": ts,
        "source": payload.source,
        "items_len": len(payload.items),
        "top_n": 20,
        **summary,
        **ranks,
    }

    if settings.GCS_BUCKET:
        try:
            save_json_to_gcs(resp, _latest_object_name())
        except Exception as exc:
            print(f"failed to save latest.json: {exc}")

    if resp.get("top_amount"):
        print("TOP_AMOUNT:")
        for r in resp["top_amount"][:5]:
            print(f"  {r['raw_name']} {r['amount']}")
    if resp.get("top_growth_per_min"):
        print("TOP_GROWTH(/min):")
        for r in resp["top_growth_per_min"][:5]:
            print(f"  {r['raw_name']} +{r['growth_per_min']}/min")

    print(json.dumps({"type": "ingest_summary", **resp}, ensure_ascii=False))
    return resp

@router.get("/dashboard")
def dashboard(top_n: int = Query(10, ge=5, le=20)) -> Dict[str, Any]:
    if not settings.GCS_BUCKET:
        raise HTTPException(status_code=503, detail="GCS_BUCKET is not configured")

    object_name = _latest_object_name()
    try:
        data = load_json_from_gcs(object_name)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"failed to load latest dashboard from GCS: gs://{settings.GCS_BUCKET}/{object_name}: {exc}",
        )
    if data is None:
        raise HTTPException(
            status_code=404,
            detail=f"latest dashboard not found: gs://{settings.GCS_BUCKET}/{object_name}",
        )

    top = data.get("top")
    if isinstance(top, dict):
        for metric in top.values():
            if not isinstance(metric, dict):
                continue
            for kind, items in metric.items():
                if isinstance(items, list):
                    metric[kind] = items[:top_n]

    for key in (
    "top_amount_items","top_amount_fluids","top_amount_gases",
    "top_growth_per_min_items","top_growth_per_min_fluids","top_growth_per_min_gases",
    "top_decrease_per_min_items","top_decrease_per_min_fluids","top_decrease_per_min_gases",
    ):
        if isinstance(data.get(key), list):
            data[key] = data[key][:top_n]

    data["top_n"] = top_n
    return data

from fastapi.responses import HTMLResponse

DASHBOARD_HTML = r"""
<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>AE2 Dashboard</title>
  <style>
    :root { --bg:#0b0f14; --card:#111824; --text:#e6edf3; --muted:#9fb0c0; --line:#223042; }
    body { margin:0; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial;
           background:var(--bg); color:var(--text); }
    header { position:sticky; top:0; background:rgba(11,15,20,.9); backdrop-filter: blur(8px);
             border-bottom:1px solid var(--line); padding:14px 18px; display:flex; gap:14px; align-items:center; }
    .title { font-weight:700; letter-spacing:.3px; }
    .pill { padding:6px 10px; border:1px solid var(--line); border-radius:999px; color:var(--muted); font-size:12px; }
    .wrap { padding:18px; max-width:1200px; margin:0 auto; }
    .tabs { display:flex; gap:8px; margin:14px 0; }
    .tab { padding:8px 12px; border:1px solid var(--line); border-radius:10px; background:transparent; color:var(--muted); cursor:pointer;}
    .tab.active { background:var(--card); color:var(--text); }
    .grid { display:grid; grid-template-columns: 1fr 1fr 1fr; gap:12px; }
    @media (max-width: 980px) { .grid { grid-template-columns:1fr; } }
    .card { background:var(--card); border:1px solid var(--line); border-radius:16px; padding:12px 12px 10px; }
    .card h2 { font-size:14px; margin:2px 0 10px; color:var(--muted); font-weight:600; }
    table { width:100%; border-collapse:collapse; font-size:13px; }
    th, td { padding:6px 4px; border-bottom:1px solid rgba(34,48,66,.6); }
    th { text-align:left; color:var(--muted); font-weight:600; }
    .name { max-width: 320px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .barwrap { height:10px; background:rgba(34,48,66,.5); border-radius:999px; overflow:hidden; }
    .bar { height:100%; width:0%; }
    .bar.amount { background: rgba(130,180,255,.9); }
    .bar.growth { background: rgba(120,220,170,.9); }
    .bar.decrease { background: rgba(255,120,140,.9); }
    .row { display:flex; gap:10px; align-items:center; }
    .val { min-width:72px; text-align:right; color:var(--text); }
    .muted { color:var(--muted); }
    .right { margin-left:auto; display:flex; gap:10px; align-items:center; }
    input[type="range"] { width:160px; }
    button { background:var(--card); border:1px solid var(--line); color:var(--text);
             border-radius:10px; padding:8px 12px; cursor:pointer; }
    button:hover { filter:brightness(1.08); }
    .err { margin:10px 0; padding:10px 12px; border:1px solid #5a2a2a; background:rgba(120,30,30,.25); border-radius:12px; }
  </style>
</head>
<body>
  <header>
    <div class="title">AE2 Dashboard</div>
    <span class="pill" id="meta">loading…</span>
    <div class="right">
        <label class="pill" style="display:flex; gap:8px; align-items:center;">
        <input id="auto" type="checkbox" />
        <span>Auto</span>
        </label>

        <label class="pill" style="display:flex; gap:8px; align-items:center;">
        <input id="perHour" type="checkbox" />
        <span>/hour</span>
        </label>

        <span class="muted">TopN</span>
        <input id="topn" type="range" min="5" max="20" step="1" value="10" />
        <span class="pill" id="topnVal">10</span>
        <button id="refresh">更新</button>
    </div>
  </header>

  <div class="wrap">
    <div id="err" class="err" style="display:none;"></div>

    <div class="tabs">
      <button class="tab active" data-kind="item">Items</button>
      <button class="tab" data-kind="fluid">Fluids</button>
      <button class="tab" data-kind="gas">Gases</button>
    </div>

    <div class="grid">
      <div class="card">
        <h2>Amount</h2>
        <div id="amount"></div>
      </div>
      <div class="card">
        <h2>Growth (/min)</h2>
        <div id="growth"></div>
      </div>
      <div class="card">
        <h2>Decrease (/min)</h2>
        <div id="decrease"></div>
      </div>
    </div>
  </div>

<script>
let activeKind = "item";

function fmt(n){
  if (n === null || n === undefined) return "-";
  if (typeof n !== "number") return String(n);
  // 軽い桁区切り
  return n.toLocaleString("en-US");
}

function setErr(msg){
  const el = document.getElementById("err");
  if (!msg) { el.style.display="none"; el.textContent=""; return; }
  el.style.display="block"; el.textContent = msg;
}

function prettyName(name){
  // "minecraft:stone" -> "<span class=muted>minecraft:</span>stone"
  const idx = name.indexOf(":");
  if (idx <= 0) return name;
  const ns = name.slice(0, idx+1);
  const rest = name.slice(idx+1);
  return `<span class="muted">${ns}</span>${rest}`;
}

function tableFor(list, valueKey, metricClass){
  if (!Array.isArray(list) || list.length === 0) return `<div class="muted">（データなし）</div>`;

  const perHour = document.getElementById("perHour")?.checked;
  const scale = perHour ? 60 : 1;

  const values = list.map(x => (x && typeof x[valueKey] === "number") ? x[valueKey] * scale : 0);
  const max = Math.max(...values, 1);

  const rows = list.map((x, i) => {
    const raw = (x.display_name || x.raw_name || "-");
    const v = values[i] ?? 0;
    const pct = Math.max(0, Math.min(100, (v / max) * 100));
    return `
      <tr>
        <td class="name" title="${raw}">${prettyName(raw)}</td>
        <td>
          <div class="row">
            <div class="barwrap" style="flex:1;">
              <div class="bar ${metricClass}" style="width:${pct}%;"></div>
            </div>
            <div class="val">${fmt(Math.round(v))}</div>
          </div>
        </td>
      </tr>
    `;
  }).join("");

  return `
    <table>
      <thead><tr><th>name</th><th style="width:70%;">value</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
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

  const meta = document.getElementById("meta");
  meta.textContent = `source=${data.source ?? "-"}  ts=${data.ts ? new Date(data.ts*1000).toLocaleString() : "-"}`;

  const top = data.top || {};
  const byMetric = (m) => (top[m] || {});
  const amount = (byMetric("amount")[activeKind] || []);
  const growth = (byMetric("growth_per_min")[activeKind] || []);
  const decrease = (byMetric("decrease_per_min")[activeKind] || []);

    document.getElementById("amount").innerHTML = tableFor(amount, "amount", "amount");
    document.getElementById("growth").innerHTML = tableFor(growth, "growth_per_min", "growth");
    document.getElementById("decrease").innerHTML = tableFor(decrease, "decrease_per_min", "decrease");
}

document.getElementById("topn").addEventListener("input", (e) => {
  document.getElementById("topnVal").textContent = e.target.value;
});

document.getElementById("refresh").addEventListener("click", load);

document.querySelectorAll(".tab").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    activeKind = btn.dataset.kind;
    load();
  });
});

load();

let timer = null;

function setAuto(on){
  if (timer) { clearInterval(timer); timer = null; }
  if (on) timer = setInterval(load, 10000);
}

document.getElementById("auto").addEventListener("change", (e) => {
  setAuto(e.target.checked);
});

document.getElementById("perHour").addEventListener("change", () => {
  load();
});
</script>
</body>
</html>
"""

@router.get("/dashboard/ui", response_class=HTMLResponse)
def dashboard_ui() -> HTMLResponse:
    return HTMLResponse(DASHBOARD_HTML)
