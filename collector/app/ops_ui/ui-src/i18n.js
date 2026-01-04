// @ts-check

/** @typedef {"fluid"|"gas"|undefined} ResourceKind */
/** @typedef {{ normalized: unknown, kind: ResourceKind }} ResourceIdInfo */

/** @type {Record<string, { ja?: string, en?: string }>} */
let displayNameDict = {};
/** @type {"ja"|"en"|"both"} */
let displayNameLang = "ja";

/**
 * @param {unknown} id
 * @returns {ResourceIdInfo}
 */
export function normalizeResourceId(id) {
  if (typeof id !== "string") return { normalized: id, kind: undefined };
  const parts = id.split(":");
  if (parts.length >= 3 && (parts[0] === "fluid" || parts[0] === "gas")) {
    return { normalized: parts.slice(1).join(":"), kind: parts[0] };
  }
  return { normalized: id, kind: undefined };
}

/**
 * @param {unknown} id
 * @returns {{ id: unknown, kind: ResourceKind }}
 */
export function normalizeId(id) {
  const info = normalizeResourceId(id);
  const normalized = typeof info.normalized === "string" ? info.normalized : id;
  return { id: normalized, kind: info.kind };
}

/**
 * @returns {"ja"|"en"|"both"}
 */
export function resolveDisplayNameLang() {
  const param = new URLSearchParams(window.location.search).get("lang");
  if (param === "ja" || param === "en" || param === "both") return param;
  return "ja";
}

/**
 * @returns {Promise<void>}
 */
export async function loadDisplayNameDict() {
  displayNameLang = resolveDisplayNameLang();
  try {
    const res = await fetch("/dashboard/ui/static/i18n/display_names.json", { cache: "no-store" });
    if (!res.ok) return;
    const data = await res.json();
    if (data && typeof data === "object") displayNameDict = data;
  } catch (_e) {
    // Optional file; ignore load errors.
  }
}

/**
 * @param {unknown} id
 * @returns {string}
 */
export function autoDisplayNameFromId(id) {
  if (typeof id !== "string") return "";
  const base = id.includes(":") ? id.split(":")[1] : id;
  const spaced = base.replace(/[_\.-]+/g, " ").replace(/\s+/g, " ").trim();
  if (!spaced) return "";
  return spaced
    .split(" ")
    .map(w => w ? w[0].toUpperCase() + w.slice(1).toLowerCase() : "")
    .join(" ");
}

/**
 * @param {unknown} id
 * @param {"ja"|"en"|"both"} [lang]
 * @returns {string}
 */
export function getDisplayName(id, lang) {
  if (typeof id !== "string" || !id) return "-";
  const info = normalizeResourceId(id);
  const normalized = typeof info.normalized === "string" ? info.normalized : id;
  const entry = displayNameDict[normalized];
  const preferred = lang || displayNameLang || "ja";
  if (entry && typeof entry === "object") {
    const ja = typeof entry.ja === "string" ? entry.ja : "";
    const en = typeof entry.en === "string" ? entry.en : "";
    if (preferred === "both") {
      if (ja && en) return `${ja} (${en})`;
      if (ja) return ja;
      if (en) return en;
    } else if (preferred === "en") {
      if (en) return en;
      if (ja) return ja;
    } else {
      if (ja) return ja;
      if (en) return en;
    }
  }
  const auto = autoDisplayNameFromId(normalized);
  if (auto) return auto;
  return normalized || id;
}
