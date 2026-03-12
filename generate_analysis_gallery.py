#!/usr/bin/env python3
"""
Generate HTML gallery from accepted_with_analysis.json showing
scene labels, segmentation scores, and building match.
"""
import argparse
import html
import json
from pathlib import Path


def escape(x):
    return html.escape("" if x is None else str(x))


def build_card(rec: dict) -> tuple[str, str]:
    """Build HTML card for one record. Returns (card_html, data_key)."""
    img_id = rec.get("id", "")
    url = rec.get("thumb_original_url", "")

    best = rec.get("best_match") or {}
    osm_id = best.get("osm_id", "-")
    score = best.get("score")
    score_str = f"{score:.3f}" if score is not None else "-"

    scene = rec.get("scene_top1") or {}
    scene_label = scene.get("label", "-")
    scene_prob = scene.get("prob")
    scene_reject = rec.get("scene_reject")
    scene_str = f"{scene_label}" + (f" ({scene_prob:.2f})" if scene_prob is not None else "")
    if scene_reject:
        scene_str += " [REJECTED]"

    seg = rec.get("segmentation") or {}
    bldg_frac = seg.get("building_frac")
    seg_reason = seg.get("reason", "-")
    bldg_str = f"{bldg_frac:.2f}" if bldg_frac is not None else "-"

    key_parts = [img_id, osm_id, scene_label, seg_reason, "rejected" if scene_reject else ""]
    data_key = " ".join(str(p) for p in key_parts).lower()

    img_html = ""
    if url and url.startswith("http"):
        img_html = f'<a href="{escape(url)}" target="_blank" rel="noreferrer"><img src="{escape(url)}" loading="lazy"></a>'
    else:
        img_html = f'<div class="missing">No URL</div>'

    card_class = "card scene-reject" if scene_reject else "card"
    card = (
        f'<div class="{card_class}" data-key="{escape(data_key)}">'
        f"{img_html}"
        f'<div class="cap">'
        f'<div class="id">{escape(img_id)}</div>'
        f'<div class="row"><span class="label">Building:</span> {escape(osm_id)} ({escape(score_str)})</div>'
        f'<div class="row"><span class="label">Scene:</span> {escape(scene_str)}</div>'
        f'<div class="row"><span class="label">Seg:</span> bldg={escape(bldg_str)} ({escape(seg_reason)})</div>'
        f"</div></div>"
    )
    return card, data_key


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--input",
        default="accepted_with_analysis.json",
        help="Path to accepted_with_analysis.json",
    )
    ap.add_argument(
        "--output",
        default="accepted_analysis_gallery.html",
        help="Output HTML path",
    )
    ap.add_argument(
        "--output-by-sequence",
        default="accepted_analysis_gallery_by_sequence.html",
        help="Additional gallery grouped by sequence_id (if present in data)",
    )
    args = ap.parse_args()

    data = json.loads(Path(args.input).read_text(encoding="utf-8"))

    cards = []
    for rec in data:
        card, _ = build_card(rec)
        cards.append(card)

    html_out = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<title>Accepted with Analysis ({len(data)} images)</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Arial, sans-serif; margin: 16px; }}
h1 {{ font-size: 20px; margin: 0 0 8px 0; }}
.topbar {{ position: sticky; top: 0; background: white; padding: 10px 0; border-bottom: 1px solid #eee; z-index: 10; margin-bottom: 16px; }}
input {{ width: 100%; max-width: 500px; padding: 8px 10px; font-size: 14px; }}
.small {{ color:#666; font-size: 12px; margin-bottom: 12px; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 14px; }}
.card {{ border: 1px solid #ddd; border-radius: 10px; overflow: hidden; background: #fff; }}
.card.scene-reject {{ border-color: #c44; background: #fff8f8; }}
.card img {{ width: 100%; height: 200px; object-fit: cover; display: block; background: #f3f3f3; }}
.cap {{ padding: 10px; font-size: 12px; }}
.id {{ font-weight: 600; font-size: 13px; margin-bottom: 6px; }}
.row {{ color: #444; margin: 3px 0; }}
.row .label {{ color: #666; font-weight: 500; }}
.missing {{ width: 100%; height: 200px; display: flex; align-items: center; justify-content: center; background: #f3f3f3; color: #666; }}
a {{ color: inherit; text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
</style>
</head>
<body>
<div class="topbar">
  <h1>Accepted with Analysis ({len(data)} images)</h1>
  <input id="q" placeholder="Filter by id, building, scene, or seg reason..." oninput="filter()"/>
</div>
<div class="small">Scene = ResNet Places365. Seg = Mask2Former (building_frac, reason).</div>
<div class="grid">
{chr(10).join(cards)}
</div>
<script>
function filter() {{
  const q = document.getElementById('q').value.toLowerCase();
  document.querySelectorAll('.card').forEach(el => {{
    el.style.display = (el.getAttribute('data-key') || '').includes(q) ? '' : 'none';
  }});
}}
</script>
</body>
</html>"""

    Path(args.output).write_text(html_out, encoding="utf-8")
    print(f"Wrote {args.output}")

    # Group by sequence and write additional gallery
    by_seq = {}
    for rec in data:
        seq_id = rec.get("sequence_id")
        if seq_id is not None:
            key = str(seq_id)
            if key not in by_seq:
                by_seq[key] = []
            by_seq[key].append(rec)

    if by_seq:
        seq_sections = []
        for seq_id, recs in sorted(by_seq.items(), key=lambda x: -len(x[1])):
            seq_cards = []
            for rec in recs:
                card, data_key = build_card(rec)
                seq_cards.append(card)
            seq_sections.append(
                f'<div class="seq-section">'
                f'<h2>Sequence {escape(seq_id)} ({len(recs)} images)</h2>'
                f'<div class="grid">{" ".join(seq_cards)}</div>'
                f"</div>"
            )
        seq_html = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<title>Accepted with Analysis by Sequence</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Arial, sans-serif; margin: 16px; }}
h1 {{ font-size: 20px; margin: 0 0 8px 0; }}
h2 {{ font-size: 16px; margin: 20px 0 8px 0; color: #333; }}
.seq-section {{ margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid #eee; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 14px; }}
.card {{ border: 1px solid #ddd; border-radius: 10px; overflow: hidden; background: #fff; }}
.card.scene-reject {{ border-color: #c44; background: #fff8f8; }}
.card img {{ width: 100%; height: 200px; object-fit: cover; display: block; background: #f3f3f3; }}
.cap {{ padding: 10px; font-size: 12px; }}
.id {{ font-weight: 600; font-size: 13px; margin-bottom: 6px; }}
.row {{ color: #444; margin: 3px 0; }}
.row .label {{ color: #666; font-weight: 500; }}
.missing {{ width: 100%; height: 200px; display: flex; align-items: center; justify-content: center; background: #f3f3f3; color: #666; }}
a {{ color: inherit; text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
</style>
</head>
<body>
<h1>Accepted with Analysis, grouped by Mapillary sequence</h1>
<div class="small">Scene = ResNet Places365. Seg = Mask2Former (building_frac, reason).</div>
{chr(10).join(seq_sections)}
</body>
</html>"""
        out_seq = Path(args.output_by_sequence)
        out_seq.write_text(seq_html, encoding="utf-8")
        print(f"Wrote {out_seq} ({len(by_seq)} sequences)")


if __name__ == "__main__":
    main()
