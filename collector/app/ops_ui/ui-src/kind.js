// @ts-check

/**
 * Centralize Kind <-> KindKey conversions so UI code stays on singular Kind.
 */

/**
 * @typedef {import("./types.ts").Kind} Kind
 * @typedef {import("./types.ts").KindKey} KindKey
 */

/** @type {Kind[]} */
export const KINDS = ["item", "fluid", "gas"];

/** @type {Record<Kind, KindKey>} */
const KIND_KEY_MAP = {
  item: "items",
  fluid: "fluids",
  gas: "gases",
};

/**
 * @param {Kind} kind
 * @returns {KindKey}
 */
export function kindToKey(kind) {
  return KIND_KEY_MAP[kind];
}
