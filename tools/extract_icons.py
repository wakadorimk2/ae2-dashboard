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

def scan_jar(jar_path: Path) -> List[Tuple[str, str, str, str]]:
    """
    Returns list of (modid, kind, rel, zip_entry)
      kind: 'item' or 'block'
      rel:  path under textures/kind without '.png' (e.g. 'ingot/tin')
    """
    out = []
    with zipfile.ZipFile(jar_path) as z:
        for name in z.namelist():
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

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mods", required=True, help="mods folder containing .jar files")
    ap.add_argument("--out", required=True, help="output folder for extracted icons")
    ap.add_argument("--max-per-mod", type=int, default=0, help="limit extracted png count per mod (0 = no limit)")
    args = ap.parse_args()

    mods_dir = Path(args.mods)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    index: Dict[str, List[str]] = {}  # key -> list of web paths (candidates)

    jars = sorted(mods_dir.glob("*.jar"))
    if not jars:
        raise SystemExit(f"No .jar found in {mods_dir}")

    for jar in jars:
        try:
            entries = scan_jar(jar)
        except zipfile.BadZipFile:
            continue

        if not entries:
            continue

        per_mod_count = 0
        with zipfile.ZipFile(jar) as z:
            for modid, kind, rel, entry in entries:
                if args.max_per_mod and per_mod_count >= args.max_per_mod:
                    break

                # Save as: out/<modid>/<kind>/<rel>.png
                dest = out_dir / modid / kind / (safe_name(rel) + ".png")
                if dest.exists():
                    # keep first found
                    continue

                extract_png(z, entry, dest)
                per_mod_count += 1

                # Build candidate keys:
                #  - item-like resource: <modid>:<rel_last> (best effort)
                #  - also keep full rel for niche cases
                rel_last = rel.split("/")[-1]
                key_simple = f"{modid}:{rel_last}"
                key_full = f"{modid}:{rel}"

                web_path = f"/dashboard/ui/static/icons/{modid}/{kind}/{safe_name(rel)}.png"
                index.setdefault(key_simple, []).append(web_path)
                if key_full != key_simple:
                    index.setdefault(key_full, []).append(web_path)

    # write index
    idx_path = out_dir / "icon_index.json"
    with open(idx_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    print(f"Done. icons -> {out_dir}")
    print(f"Index -> {idx_path}")
    print(f"Keys: {len(index)}")

if __name__ == "__main__":
    main()
