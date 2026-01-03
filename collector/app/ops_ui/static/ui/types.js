// @ts-check

/**
 * @typedef {Object} TopEntry
 * @property {string} [raw_name]
 * @property {string} [display_name]
 * @property {number} [amount]
 * @property {number} [growth_per_min]
 * @property {number} [decrease_per_min]
 */

/**
 * @typedef {Object} DashboardData
 * @property {{ [metric: string]: { [kind: string]: TopEntry[] } }} [top]
 * @property {string} [source]
 * @property {number} [ts]
 */

export {};
