(() => {
  "use strict";

  // UI intent: shared scale utils for ops_ui bar charts and future ranking/cards/heatmap.
  // Recommended defaults: amount => log1p, delta => asinh + p95 k.

  function toFiniteNumber(v, fallback) {
    return (typeof v === "number" && Number.isFinite(v)) ? v : fallback;
  }

  function clamp(v, min, max) {
    let lo = toFiniteNumber(min, 0);
    let hi = toFiniteNumber(max, 0);
    if (lo > hi) {
      const t = lo;
      lo = hi;
      hi = t;
    }
    const val = toFiniteNumber(v, lo);
    if (val < lo) return lo;
    if (val > hi) return hi;
    return val;
  }

  function clamp01(v) {
    return clamp(v, 0, 1);
  }

  function compressAmount(x, method) {
    const val = Math.max(0, toFiniteNumber(x, 0));
    const m = method === "sqrt" ? "sqrt" : "log1p";
    return m === "sqrt" ? Math.sqrt(val) : Math.log1p(val);
  }

  function normalize01(v, vmin, vmax) {
    const lo = toFiniteNumber(vmin, 0);
    const hi = toFiniteNumber(vmax, 0);
    const denom = hi - lo;
    if (!Number.isFinite(denom) || denom <= 0) return 0;
    const t = (toFiniteNumber(v, 0) - lo) / denom;
    return clamp01(t);
  }

  function buildNormalizer(values, method) {
    const list = Array.isArray(values) ? values : [];
    const m = method === "sqrt" ? "sqrt" : "log1p";
    let min = Infinity;
    let max = -Infinity;
    for (const v of list) {
      const c = compressAmount(v, m);
      if (c < min) min = c;
      if (c > max) max = c;
    }
    if (!Number.isFinite(min) || !Number.isFinite(max) || max === min) {
      return () => 0;
    }
    return (x) => normalize01(compressAmount(x, m), min, max);
  }

  function applyMinRatio01(n01, minRatio) {
    const ratio = clamp01(toFiniteNumber(minRatio, 0.02));
    const v = clamp01(toFiniteNumber(n01, 0));
    if (ratio <= 0) return v;
    return ratio + (1 - ratio) * v;
  }

  function compressDelta(d, k) {
    const val = toFiniteNumber(d, 0);
    let kSafe = Math.abs(toFiniteNumber(k, 1));
    if (kSafe === 0) kSafe = 1;
    return Math.asinh(val / kSafe);
  }

  function normalizeSigned(v, vmaxAbs) {
    const maxAbs = Math.abs(toFiniteNumber(vmaxAbs, 0));
    if (maxAbs === 0) return 0;
    const t = toFiniteNumber(v, 0) / maxAbs;
    return clamp(t, -1, 1);
  }

  function percentileAbs(values, p) {
    const list = Array.isArray(values) ? values : [];
    const arr = [];
    for (const v of list) {
      if (typeof v !== "number" || !Number.isFinite(v)) continue;
      arr.push(Math.abs(v));
    }
    if (arr.length === 0) return 0;
    let pct = toFiniteNumber(p, 0);
    pct = pct > 1 ? pct / 100 : pct;
    pct = clamp01(pct);
    arr.sort((a, b) => a - b);
    if (arr.length === 1) return arr[0];
    const idx = pct * (arr.length - 1);
    const lo = Math.floor(idx);
    const hi = Math.ceil(idx);
    if (lo === hi) return arr[lo];
    const t = idx - lo;
    return arr[lo] + (arr[hi] - arr[lo]) * t;
  }

  function buildDeltaNormalizer(deltas, kStrategy, fixedK) {
    const list = Array.isArray(deltas) ? deltas : [];
    const options = (kStrategy && typeof kStrategy === "object") ? kStrategy : {
      kStrategy,
      fixedK,
    };
    const strategy = options.kStrategy === "fixed" ? "fixed" : "p95";
    const pct = options.percentile !== undefined ? options.percentile : 0.95;
    let k = strategy === "fixed" ? toFiniteNumber(options.fixedK, 0) : percentileAbs(list, pct);
    if (!Number.isFinite(k) || k <= 0) k = 1;

    let maxAbs = 0;
    const maxAbsPercentile = options.maxAbsPercentile;
    if (maxAbsPercentile !== undefined) {
      const compressedAbs = [];
      for (const d of list) {
        const c = Math.abs(compressDelta(d, k));
        if (Number.isFinite(c)) compressedAbs.push(c);
      }
      maxAbs = percentileAbs(compressedAbs, maxAbsPercentile);
    } else {
      for (const d of list) {
        const c = Math.abs(compressDelta(d, k));
        if (c > maxAbs) maxAbs = c;
      }
    }
    if (!Number.isFinite(maxAbs) || maxAbs <= 0) maxAbs = 1;

    return {
      k,
      norm: (d) => normalizeSigned(compressDelta(d, k), maxAbs),
    };
  }

  function toPerMinute(value, unit) {
    const v = toFiniteNumber(value, 0);
    if (!unit) return v;
    const u = String(unit).toLowerCase();
    if (u === "per_min" || u === "min" || u === "/min") return v;
    if (u === "per_sec" || u === "sec" || u === "s" || u === "/s") return v * 60;
    if (u === "per_hour" || u === "hour" || u === "h" || u === "/h") return v / 60;
    return v;
  }

  // Append ?scale_test=1 to run a console-based smoke test in the browser.
  function runScaleSelfTest() {
    const amounts = [0, 1, 10, 100, 1000, 1e6];
    const deltas = [-5000, -100, -10, 0, 10, 100, 5000];
    const amountNorm = buildNormalizer(amounts, "log1p");
    const deltaNorm = buildDeltaNormalizer(deltas, { kStrategy: "p95", percentile: 0.95 });
    const minRatioDemo = amounts.map(a => applyMinRatio01(amountNorm(a), 0.02).toFixed(3));
    console.log("[scale] amounts", amounts.map(a => amountNorm(a).toFixed(3)));
    console.log("[scale] minRatio", minRatioDemo);
    console.log("[scale] delta k", deltaNorm.k, deltas.map(d => deltaNorm.norm(d).toFixed(3)));
    console.log("[scale] per_min from /s", toPerMinute(2, "per_sec"));
  }

  if (typeof window !== "undefined") {
    window.ScaleUtils = {
      clamp,
      clamp01,
      compressAmount,
      normalize01,
      buildNormalizer,
      applyMinRatio01,
      compressDelta,
      normalizeSigned,
      percentileAbs,
      buildDeltaNormalizer,
      toPerMinute,
      runScaleSelfTest,
    };

    const params = new URLSearchParams(window.location.search);
    if (params.get("scale_test") === "1") runScaleSelfTest();
  }
})();
