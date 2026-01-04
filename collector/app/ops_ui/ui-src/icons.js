// @ts-check

import { normalizeId } from "./i18n.js";

/** @type {Record<string, string[]>} */
let iconIndex = {};
/** @type {Promise<void> | null} */
let iconIndexPromise = null;

/**
 * @returns {Promise<void>}
 */
export async function loadIconIndex() {
  if (iconIndexPromise) return iconIndexPromise;
  iconIndexPromise = (async () => {
    try {
      const res = await fetch("/dashboard/ui/static/icons/icon_index.json", { cache: "no-store" });
      if (!res.ok) return;
      const data = await res.json();
      if (data && typeof data === "object") iconIndex = data;
    } catch (_e) {
      iconIndex = {};
    }
  })();
  return iconIndexPromise;
}

/**
 * @param {unknown} rawId
 * @returns {string | null}
 */
export function getIconUrl(rawId) {
  const info = normalizeId(rawId);
  if (!info || typeof info.id !== "string" || !info.id) return null;
  const candidates = iconIndex[info.id];
  if (!Array.isArray(candidates) || candidates.length === 0) return null;
  const first = candidates.find(v => typeof v === "string" && v);
  if (!first) return null;
  return first;
}
