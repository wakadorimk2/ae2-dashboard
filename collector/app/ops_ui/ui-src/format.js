// @ts-check

import { kindUnit, state } from "./state.js";

/** @typedef {import("./types.js").Kind} Kind */

/**
 * @param {unknown} n
 * @returns {string}
 */
export function fmtRaw(n) {
  if (n === null || n === undefined) return "-";
  if (typeof n !== "number" || Number.isNaN(n)) return String(n);
  return n.toLocaleString("en-US");
}

/**
 * @param {string} str
 * @returns {string}
 */
export function trimZeros(str) {
  return str.replace(/\.0+$/, "").replace(/(\.\d*[1-9])0+$/, "$1");
}

/**
 * @param {string} unit
 * @param {number} val
 * @returns {number}
 */
function compactDecimals(unit, val) {
  if (unit === "K") return val >= 100 ? 0 : 1;
  if (val >= 100) return 0;
  if (val >= 10) return 1;
  return 2;
}

/**
 * @param {unknown} n
 * @returns {string}
 */
export function fmtCompact(n) {
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
  for (const u of units) {
    if (abs >= u.v) {
      const val = abs / u.v;
      const decimals = compactDecimals(u.s, val);
      return `${sign}${trimZeros(val.toFixed(decimals))}${u.s}`;
    }
  }
  return `${sign}${fmtRaw(abs)}`;
}

/**
 * @param {unknown} n
 * @returns {string}
 */
export function formatValue(n) {
  return state.formatMode === "compact" ? fmtCompact(n) : fmtRaw(n);
}

/**
 * @param {string} name
 * @returns {string}
 */
export function prettyName(name) {
  const idx = name.indexOf(":");
  if (idx <= 0) return name;
  const ns = name.slice(0, idx + 1);
  const rest = name.slice(idx + 1);
  return `<span class="muted">${ns}</span>${rest}`;
}

/**
 * @param {Kind} kind
 * @returns {string}
 */
export function unitFor(kind) {
  return kindUnit[kind] || "";
}

/**
 * @param {unknown} n
 * @returns {number}
 */
export function scaleValue(n) {
  if (typeof n !== "number") return 0;
  // NOTE: /hour toggle removed; keep /min fixed to avoid DOM dependency.
  return n;
}
