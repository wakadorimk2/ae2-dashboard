#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import zipfile
from pathlib import Path
from typing import Dict, List, Tuple

PNG_RE = re.compile(r"^assets/([^/]+)/textures/(item|block)/(.+)\.png$")

def safe_name(s: str) -> str:
    # filesystem-friendly
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", s)

def scan_jar(names: List[str]) -> List[Tuple[str, str, str, str]]:
    """
    Returns list of (modid, kind, rel, zip_entry)
      kind: 'item' or 'block'
      rel:  path under textures/kind without '.png' (e.g. 'ingot/tin')
    """
    out = []
    for name in names:
        m = PNG_RE.match(name)
        if not m:
            continue
        modid, kind, rel = m.group(1), m.group(2), m.group(3)
        out.append((modid, kind, rel, name))
    return out

def extract_png(z: zipfile.ZipFile, entry: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with z.open(entry) as src, open(dest, "wb") as f:
        f.write(src.read())

def add_unique(index: Dict[str, List[str]], key: str, value: str) -> None:
    existing = index.get(key)
    if existing is None:
        index[key] = [value]
        return
    if value not in existing:
        existing.append(value)

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mods", required=True, help="mods folder containing .jar files or a single .jar file")
    ap.add_argument("--out", required=True, help="output folder for extracted icons")
    ap.add_argument("--max-per-mod", type=int, default=0, help="limit extracted png count per mod (0 = no limit)")
    args = ap.parse_args()

    mods_path = Path(args.mods)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    index: Dict[str, List[str]] = {}  # key -> list of web paths (candidates)
    idx_path = out_dir / "icon_index.json"
    if idx_path.exists():
        with open(idx_path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        if isinstance(loaded, dict):
            for key, values in loaded.items():
                if isinstance(values, list):
                    index[key] = [str(v) for v in values]

    if mods_path.is_file():
        if mods_path.suffix.lower() != ".jar":
            raise SystemExit(f"--mods must be a .jar file or a folder of .jar files: {mods_path}")
        jars = [mods_path]
    elif mods_path.is_dir():
        jars = sorted(mods_path.glob("*.jar"))
        if not jars:
            raise SystemExit(f"No .jar found in {mods_path}")
    else:
        raise SystemExit(f"--mods path not found: {mods_path}")

    print(f"Jars: {len(jars)}")
    for jar in jars[:3]:
        print(f"  {jar}")

    for jar in jars:
        try:
            with zipfile.ZipFile(jar) as z:
                names = z.namelist()
                assets_samples = [n for n in names[:10] if "assets/" in n][:2]
                if assets_samples:
                    for sample in assets_samples:
                        print(f"[{jar}] assets sample: {sample}")
                else:
                    print(f"[{jar}] assets sample: (none in first 10)")

                entries = scan_jar(names)
                print(f"[{jar}] matched pngs: {len(entries)}")

                if not entries:
                    continue

                per_mod_count = 0
                for modid, kind, rel, entry in entries:
                    if args.max_per_mod and per_mod_count >= args.max_per_mod:
                        break

                    safe_rel = safe_name(rel)
                    web_path = f"/dashboard/ui/static/icons/{modid}/{kind}/{safe_rel}.png"

                    # Build candidate keys:
                    #  - item-like resource: <modid>:<rel_last> (best effort)
                    #  - also keep full rel for niche cases
                    rel_last = rel.split("/")[-1]
                    key_simple = f"{modid}:{rel_last}"
                    key_full = f"{modid}:{rel}"

                    add_unique(index, key_simple, web_path)
                    if key_full != key_simple:
                        add_unique(index, key_full, web_path)

                    # Save as: out/<modid>/<kind>/<rel>.png
                    dest = out_dir / modid / kind / (safe_rel + ".png")
                    if dest.exists():
                        # keep first found
                        continue

                    extract_png(z, entry, dest)
                    per_mod_count += 1
        except zipfile.BadZipFile:
            continue

    # write index
    with open(idx_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    print(f"Done. icons -> {out_dir}")
    print(f"Index -> {idx_path}")
    print(f"Keys: {len(index)}")

if __name__ == "__main__":
    main()
