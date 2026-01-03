// @ts-check

/**
 * @typedef {"item"|"fluid"|"gas"} Kind
 */
// NOTE: UI uses singular kind values; data types in `ui/types.ts` use plural keys.
/**
 * @typedef {import("./types.ts").ViewMode} ViewMode
 * @typedef {"raw"|"compact"} FormatMode
 * @typedef {import("./types.ts").HeatmapCount} HeatmapCount
 * @typedef {"amount"|"delta"} HeatmapSort
 * @typedef {import("./types.ts").DashboardData} DashboardData
 * @typedef {{ kind: Kind, view: ViewMode, heatmapCount: HeatmapCount, heatmapSort: HeatmapSort, lastData?: DashboardData }} UIState
 */

export const BAR_MIN_RATIO = 0.02;
export const DELTA_UNIT = "per_min";
export const TOP_N = 200;

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

// TODO: Consider moving `timer` and `lastDeltaNormalizers` out of UI state (runtime-only).
/** @type {UIState & { formatMode: FormatMode, timer: number | null, lastDeltaNormalizers: unknown }} */
export const state = {
  kind: "item",
  view: "list",
  formatMode: "compact",
  heatmapCount: 80,
  heatmapSort: "amount",
  // NOTE: undefined until first load; raw API payload isn't normalized to DashboardData yet.
  lastData: undefined,
  timer: null,
  lastDeltaNormalizers: null,
};
