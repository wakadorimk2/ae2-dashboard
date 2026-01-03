// @ts-check

/**
 * @typedef {"item"|"fluid"|"gas"} Kind
 * @typedef {"list"|"heatmap"} ViewMode
 * @typedef {"raw"|"compact"} FormatMode
 */

export const BAR_MIN_RATIO = 0.02;
export const DELTA_UNIT = "per_min";

/** @type {Record<Kind, string>} */
export const kindLabel = {
  item: "Items",
  fluid: "Fluids",
  gas: "Gases",
};

/** @type {Record<Kind, string>} */
export const kindUnit = {
  item: "items",
  fluid: "mB",
  gas: "mB",
};

/** @type {{ activeKind: Kind, viewMode: ViewMode, formatMode: FormatMode, lastData: import("./types.js").DashboardData | null, timer: number | null, lastDeltaNormalizers: unknown }} */
export const state = {
  activeKind: "item",
  viewMode: "list",
  formatMode: "compact",
  lastData: null,
  timer: null,
  lastDeltaNormalizers: null,
};
