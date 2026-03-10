#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import html
from pathlib import Path
from typing import Dict, Any, List


# IMPORTANT: use a placeholder token we replace, so CSS braces won't break .format()
HTML_TEMPLATE = """<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>Building → Ranked Images</title>
  <style>
    body { font-family: -apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Arial,sans-serif; margin: 16px; }
    .topbar { position: sticky; top: 0; background: white; padding: 10px 0; border-bottom: 1px solid #eee; z-index: 10; }
    input { width: 520px; max-width: 95vw; padding: 8px 10px; font-size: 14px; }
    .building { margin: 18px 0 28px 0; padding-bottom: 18px; border-bottom: 1px solid #f0f0f0; }
    .title { font-size: 18px; font-weight: 650; margin: 0 0 6px 0; }
    .meta { color: #666; font-size: 13px; margin-bottom: 10px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 10px; }
    .card { border: 1px solid #eee; border-radius: 10px; overflow: hidden; background: #fff; }
    .card img { width: 100%; height: 170px; object-fit: cover; display: block; background: #fafafa; }
    .cap { padding: 8px 10px; font-size: 12px; color: #333; line-height: 1.35; }
    .cap code { font-size: 11px; color: #555; }
    .rank { font-weight: 700; }
    .missing { padding: 14px 10px; color: #a33; font-size: 12px; }
    a { color: inherit; text-decoration: none; }
    a:hover { text-decoration: underline; }
  </style>
</head>
<body>
  <div class="topbar">
    <input id="q" placeholder="Filter buildings (name/id)..." oninput="filterBuildings()"/>
  </div>

  __BODY__

<script>
function filterBuildings() {
  const q = document.getElementById('q').value.toLowerCase();
  for (const el of document.querySelectorAll('.building')) {
    const key = (el.getAttribute('data-key') || '').toLowerCase();
    el.style.display = key.includes(q) ? '' : 'none';
  }
}
</script>
</body>
</html>
"""


def safe(x: Any) -> str:
    return html.escape("" if x is None else str(x))


def load_accepted_url_index(accepted_path: Path) -> Dict[str, str]:
    """
    accepted.json is a list of image records with:
      - id
      - thumb_original_url
    """
    data = json.loads(accepted_path.read_text())
    idx: Dict[str, str] = {}
    if isinstance(data, list):
        for rec in data:
            img_id = rec.get("id")
            url = rec.get("thumb_original_url")
            if img_id is None:
                continue
            if isinstance(url, str) and url.startswith("http"):
                idx[str(img_id)] = url
    return idx


def build_section(building_key: str, rec: Dict[str, Any], url_idx: Dict[str, str], max_imgs: int) -> str:
    name = rec.get("name")
    title = name if name else f"Building {building_key}"
    tags = rec.get("tags") or {}
    images = rec.get("images") or []
    n_images = len(images)

    key_for_filter = f"{building_key} {name or ''} {tags.get('addr:housenumber','')} {tags.get('addr:street','')}".strip()
    addr = " ".join([str(tags.get("addr:housenumber", "")).strip(), str(tags.get("addr:street", "")).strip()]).strip()
    meta = " • ".join([x for x in [addr, f"{n_images} ranked images"] if x])

    cards: List[str] = []
    for rank, a in enumerate(images[:max_imgs], start=1):
        img_id = a.get("image_id")
        if img_id is None:
            continue
        img_id = str(img_id)

        url = url_idx.get(img_id)
        score = a.get("score", None)
        dmin = a.get("d_min_m", None)
        span = a.get("span_deg", None)
        align = a.get("alignment", None)

        if url:
            cards.append(
                f"""
                <div class="card">
                  <a href="{safe(url)}" target="_blank" rel="noreferrer">
                    <img src="{safe(url)}" loading="lazy">
                  </a>
                  <div class="cap">
                    <div class="rank">#{rank}</div>
                    <div><code>{safe(img_id)}</code></div>
                    <div>score={safe(score)} | d={safe(dmin)}m | span={safe(span)}° | align={safe(align)}</div>
                  </div>
                </div>
                """
            )
        else:
            cards.append(
                f"""
                <div class="card">
                  <div class="missing">
                    <div class="rank">#{rank}</div>
                    No URL for <code>{safe(img_id)}</code> in accepted.json
                  </div>
                </div>
                """
            )

    grid = f"<div class='grid'>{''.join(cards)}</div>" if cards else "<div class='meta'>No images</div>"

    return (
        f"<section class='building' data-key='{safe(key_for_filter)}'>"
        f"<div class='title'>{safe(title)}</div>"
        f"<div class='meta'>{safe(meta)}</div>"
        f"{grid}"
        f"</section>"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ranked", required=True, help="Path to building_rankings.json")
    ap.add_argument("--accepted", required=True, help="Path to accepted.json (for thumb URLs)")
    ap.add_argument("--out", default="building_gallery.html", help="Output HTML")
    ap.add_argument("--max_imgs", type=int, default=200, help="Max images per building")
    args = ap.parse_args()

    ranked = json.loads(Path(args.ranked).read_text())
    url_idx = load_accepted_url_index(Path(args.accepted))

    sections: List[str] = []
    for bkey, rec in sorted(ranked.items(), key=lambda kv: str(kv[0])):
        if isinstance(rec, dict):
            sections.append(build_section(str(bkey), rec, url_idx, args.max_imgs))

    out_html = HTML_TEMPLATE.replace("__BODY__", "\n".join(sections))
    Path(args.out).write_text(out_html, encoding="utf-8")

    print(f"Wrote: {Path(args.out).resolve()}")
    print(f"Loaded {len(url_idx)} image URLs from accepted.json")


if __name__ == "__main__":
    main()