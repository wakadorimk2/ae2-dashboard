// @ts-check

/**
 * @typedef {Object} Entry
 * @property {string} id
 * @property {string} name
 * @property {number} amount
 * @property {number} growth
 * @property {number} decrease
 * @property {string} [raw_name]
 * @property {string} [display_name]
 */

/**
 * @typedef {Object} TopByKind
 * @property {Entry[]} [items]
 * @property {Entry[]} [fluids]
 * @property {Entry[]} [gases]
 */

/**
 * @typedef {Object} DashboardTop
 * @property {TopByKind} [amount]
 * @property {TopByKind} [growth]
 * @property {TopByKind} [decrease]
 */

/**
 * @typedef {Object} DashboardData
 * @property {DashboardTop} [top]
 * @property {string} [source]
 * @property {number} [ts]
 */

export {};
