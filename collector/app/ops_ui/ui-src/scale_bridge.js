// @ts-check

/**
 * @param {unknown} n01
 * @param {unknown} minRatio
 * @returns {number}
 */
export function applyMinRatio01(n01, minRatio) {
  const utils = window.ScaleUtils;
  if (utils && typeof utils.applyMinRatio01 === "function") {
    return utils.applyMinRatio01(n01, minRatio);
  }
  const v = typeof n01 === "number" && Number.isFinite(n01) ? n01 : 0;
  const r = typeof minRatio === "number" && Number.isFinite(minRatio) ? minRatio : 0;
  const clamped = Math.max(0, Math.min(1, v));
  const ratio = Math.max(0, Math.min(1, r));
  if (ratio <= 0) return clamped;
  return ratio + (1 - ratio) * clamped;
}

/**
 * @param {unknown} value
 * @param {string} unit
 * @returns {number}
 */
export function toPerMinute(value, unit) {
  const utils = window.ScaleUtils;
  if (utils && typeof utils.toPerMinute === "function") {
    return utils.toPerMinute(value, unit);
  }
  return /** @type {number} */ (value);
}

/**
 * @param {unknown[]} values
 * @param {string} method
 * @returns {(x: unknown) => number}
 */
export function buildListNormalizer(values, method) {
  const utils = window.ScaleUtils;
  if (utils && typeof utils.buildNormalizer === "function") {
    return utils.buildNormalizer(values, method);
  }
  let max = 0;
  for (const v of values) {
    if (typeof v === "number" && Number.isFinite(v) && v > max) max = v;
  }
  if (max <= 0) return () => 0;
  return (x) => {
    if (typeof x !== "number" || !Number.isFinite(x) || x <= 0) return 0;
    const t = x / max;
    if (t <= 0) return 0;
    if (t >= 1) return 1;
    return t;
  };
}
