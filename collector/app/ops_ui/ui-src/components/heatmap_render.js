// @ts-check

import { getIconUrl } from "../icons.js";
import { formatValue } from "../format.js";
import { toNumber } from "./heatmap_model.js";

/** @typedef {import("../types.js").UiHeatmapEntry} UiHeatmapEntry */
/** @typedef {UiHeatmapEntry & { deltaScaled: number }} UiHeatmapEntryScaled */

/**
 * @param {number} value
 * @param {number} min
 * @param {number} max
 * @returns {number}
 */
function clamp(value, min, max) {
  const v = toNumber(value, min);
  return Math.min(max, Math.max(min, v));
}

/**
 * @param {number} deltaNorm
 * @returns {string}
 */
function colorForDelta(deltaNorm) {
  const v = clamp(deltaNorm, -1, 1);
  const t = Math.abs(v);
  const hue = v >= 0 ? 140 : 5;
  const sat = Math.round(25 + 55 * t);
  const light = Math.round(22 + 18 * (1 - t));
  return `hsl(${hue}, ${sat}%, ${light}%)`;
}

/**
 * @param {HTMLElement} container
 * @param {Array<{ x: number, y: number, w: number, h: number, item: UiHeatmapEntryScaled }>} tiles
 * @param {string} unit
 * @param {string} kind
 * @param {((entry: UiHeatmapEntry, event: MouseEvent | KeyboardEvent) => void) | undefined} onTileClick
 */
export function renderTiles(container, tiles, unit, kind, onTileClick) {
  const frag = document.createDocumentFragment();
  for (const tile of tiles) {
    const entry = tile.item;
    const amount = toNumber(entry.amount, 0);
    const delta = toNumber(entry.delta, 0);
    const deltaScaled = toNumber(entry.deltaScaled, 0);
    const displayName = entry.name || "-";

    const el = document.createElement("div");
    el.className = "heatmap-tile";
    el.dataset.id = `${kind}:${entry.raw}`;
    el.tabIndex = 0;
    const w = Math.max(0, tile.w);
    const h = Math.max(0, tile.h);
    el.style.left = `${tile.x}px`;
    el.style.top = `${tile.y}px`;
    el.style.width = `${w}px`;
    el.style.height = `${h}px`;
    el.style.setProperty("--tile-bg", colorForDelta(deltaScaled));

    if (w < 44 || h < 30) {
      el.classList.add("tiny");
    } else if (w < 80 || h < 42) {
      el.classList.add("small");
    }

    const deltaText = `${delta > 0 ? "+" : ""}${formatValue(delta)}`;
    el.title = `${displayName}\nAmount: ${formatValue(amount)} ${unit}\nDelta: ${deltaText} /min`;

    const showLabel = w >= 48 && h >= 30;
    if (showLabel) {
      const label = document.createElement("div");
      label.className = "heatmap-label";
      const showIcon = w >= 80 && h >= 44;
      if (showIcon) {
        const iconUrl = getIconUrl(entry.raw);
        if (iconUrl) {
          const icon = document.createElement("img");
          icon.className = "item-icon";
          icon.src = iconUrl;
          icon.alt = "";
          icon.loading = "lazy";
          icon.decoding = "async";
          icon.onerror = () => { icon.style.display = "none"; };
          label.appendChild(icon);
        }
      }
      const text = document.createElement("span");
      text.textContent = displayName;
      label.appendChild(text);
      el.appendChild(label);
    }

    if (typeof onTileClick === "function") {
      el.addEventListener("click", event => onTileClick(entry, event));
      el.addEventListener("keydown", event => {
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        onTileClick(entry, event);
      });
    }

    frag.appendChild(el);
  }
  container.appendChild(frag);
}
