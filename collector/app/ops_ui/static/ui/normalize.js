// @ts-check

/**
 * Normalize `/dashboard` response into the UI DashboardData shape.
 *
 * @param {unknown} raw
 * @returns {import("./types.ts").DashboardData}
 */
export function normalizeDashboardData(raw) {
  const data = (raw && typeof raw === "object") ? /** @type {Record<string, unknown>} */ (raw) : {};
  const top = normalizeTop(data.top);
  /** @type {import("./types.ts").DashboardData} */
  const out = {};
  if (top) out.top = top;
  if (typeof data.source === "string") out.source = data.source;
  if (typeof data.ts === "number") out.ts = data.ts;
  return out;
}

/**
 * @param {unknown} rawTop
 * @returns {import("./types.ts").DashboardTop | undefined}
 */
function normalizeTop(rawTop) {
  if (!rawTop || typeof rawTop !== "object") return undefined;
  const top = /** @type {Record<string, unknown>} */ (rawTop);
  /** @type {import("./types.ts").DashboardTop} */
  const out = {};
  for (const metric of ["amount", "growth", "decrease"]) {
    const rawMetric = pickMetric(top, metric);
    /** @type {import("./types.ts").TopByKind} */
    const byKind = {};
    for (const kind of ["item", "fluid", "gas"]) {
      const kindKey = kindToKey(kind);
      const list = normalizeList(rawMetric?.[kind] ?? rawMetric?.[kindKey], metric);
      byKind[kindKey] = list;
    }
    out[metric] = byKind;
  }
  return out;
}

/**
 * @param {Record<string, unknown>} top
 * @param {import("./types.ts").Metric} metric
 * @returns {Record<string, unknown>}
 */
function pickMetric(top, metric) {
  const key = metric === "growth"
    ? "growth_per_min"
    : (metric === "decrease" ? "decrease_per_min" : "amount");
  const raw = top[key] ?? top[metric];
  return (raw && typeof raw === "object") ? /** @type {Record<string, unknown>} */ (raw) : {};
}

/**
 * @param {unknown} list
 * @param {import("./types.ts").Metric} metric
 * @returns {import("./types.ts").Entry[]}
 */
function normalizeList(list, metric) {
  if (!Array.isArray(list)) return [];
  return list
    .map(entry => normalizeEntry(entry, metric))
    .filter((entry) => entry);
}

/**
 * @param {unknown} entry
 * @param {import("./types.ts").Metric} metric
 * @returns {import("./types.ts").Entry | null}
 */
function normalizeEntry(entry, metric) {
  if (!entry || typeof entry !== "object") return null;
  const obj = /** @type {Record<string, unknown>} */ (entry);
  const rawName = pickString(obj.raw_name)
    || pickString(obj.id)
    || pickString(obj.name)
    || pickString(obj.display_name)
    || "-";
  const displayName = pickString(obj.display_name) || pickString(obj.name) || rawName;
  const value = pickNumber(obj[metric])
    ?? pickNumber(obj[metric === "growth" ? "growth_per_min" : (metric === "decrease" ? "decrease_per_min" : "amount")])
    ?? 0;
  /** @type {import("./types.ts").Entry} */
  const out = {
    id: rawName,
    name: displayName,
    amount: 0,
    growth: 0,
    decrease: 0,
    raw_name: rawName,
    display_name: displayName,
  };
  if (metric === "amount") out.amount = value;
  if (metric === "growth") out.growth = value;
  if (metric === "decrease") out.decrease = value;
  return out;
}

/**
 * @param {unknown} value
 * @returns {string | null}
 */
function pickString(value) {
  return typeof value === "string" && value.length > 0 ? value : null;
}

/**
 * @param {unknown} value
 * @returns {number | null}
 */
function pickNumber(value) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

/**
 * @param {import("./types.ts").Kind} kind
 * @returns {import("./types.ts").KindKey}
 */
function kindToKey(kind) {
  return kind === "fluid" ? "fluids" : (kind === "gas" ? "gases" : "items");
}
