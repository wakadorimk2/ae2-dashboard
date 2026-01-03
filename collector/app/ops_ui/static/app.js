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
