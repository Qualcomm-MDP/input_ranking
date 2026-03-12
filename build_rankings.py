#!/usr/bin/env python3
"""
Convert accepted.json to building_rankings.json (buildings -> ranked images).
Also generates accepted_gallery.html and rejected_gallery.html from the JSON files.
"""
import argparse
import html
import json
from pathlib import Path


def build_osm_metadata_index(osm_source_path: Path) -> dict:
    """Extract building name and tags from m_out.json / out.json osm_raw."""
    data = json.loads(osm_source_path.read_text(encoding="utf-8"))
    index = {}
    for rec in data if isinstance(data, list) else [data]:
        elements = (rec.get("osm_raw") or {}).get("elements", [])
        for el in elements:
            el_type = el.get("type")
            el_id = el.get("id")
            if el_id is None:
                continue
            osm_id = f"{el_type}/{el_id}"
            tags = el.get("tags") or {}
            if "building" not in tags:
                continue
            index[osm_id] = {
                "name": tags.get("name"),
                "tags": {k: v for k, v in tags.items() if k.startswith("addr:")},
            }
    return index


def build_rankings(accepted_path: Path, osm_source_path: Path) -> tuple[dict, dict]:
    """Group accepted images by building osm_id and by sequence_id. Returns (by_building, by_sequence)."""
    accepted = json.loads(accepted_path.read_text(encoding="utf-8"))
    osm_meta = build_osm_metadata_index(osm_source_path) if osm_source_path else {}

    by_building = {}
    by_sequence: dict = {}
    for rec in accepted:
        best = rec.get("best_match")
        if not best:
            continue
        osm_id = best.get("osm_id")
        if not osm_id:
            continue
        img_id = rec.get("id")
        if img_id is None:
            continue
        seq_id = rec.get("sequence_id")

        img_entry = {
            "image_id": str(img_id),
            "score": best.get("score"),
            "d_min_m": best.get("d_min_m"),
            "span_deg": best.get("theta_min_deg"),
            "alignment": best.get("theta_at_dmin_deg"),
        }
        if seq_id is not None:
            img_entry["sequence_id"] = seq_id

        if osm_id not in by_building:
            meta = osm_meta.get(osm_id, {})
            by_building[osm_id] = {
                "name": meta.get("name"),
                "tags": meta.get("tags") or {},
                "images": [],
            }
        by_building[osm_id]["images"].append(img_entry)

        # Group by sequence
        if seq_id is not None:
            key = str(seq_id)
            if key not in by_sequence:
                by_sequence[key] = {"images": []}
            by_sequence[key]["images"].append(
                {**img_entry, "osm_id": osm_id}
            )

    for osm_id in by_building:
        by_building[osm_id]["images"].sort(
            key=lambda x: (x["score"] or 0), reverse=True
        )
    for seq_id in by_sequence:
        by_sequence[seq_id]["images"].sort(
            key=lambda x: (x["score"] or 0), reverse=True
        )

    return by_building, by_sequence


def _build_cards_html(
    records: list,
    meta_field: str = "best_match",
    meta_key: str = "osm_id",
) -> str:
    """Build the grid of card divs for a list of image records."""
    safe = lambda x: html.escape("" if x is None else str(x))
    cards = []
    for rec in records:
        img_id = rec.get("id", "")
        url = rec.get("thumb_original_url", "")
        if meta_field == "best_match":
            best = rec.get("best_match") or {}
            meta_val = best.get(meta_key) or rec.get("reason", "")
        else:
            best = rec.get("best_candidate") or {}
            meta_val = (best.get(meta_key) if best else None) or rec.get("reason", "")
        if url and url.startswith("http"):
            cards.append(
                f'<div class="card">'
                f'<a href="{safe(url)}" target="_blank" rel="noreferrer">'
                f'<img src="{safe(url)}" loading="lazy">'
                f"</a>"
                f'<div class="cap"><div class="id">{safe(img_id)}</div>'
                f'<div class="meta">{safe(meta_val)}</div></div></div>'
            )
        else:
            cards.append(
                f'<div class="card">'
                f'<div class="missing">No URL for {safe(img_id)}</div>'
                f'<div class="cap"><div class="id">{safe(img_id)}</div>'
                f'<div class="meta">{safe(meta_val)}</div></div></div>'
            )
    return chr(10).join(cards)


def generate_image_gallery(
    records: list,
    title: str,
    meta_field: str = "best_match",
    meta_key: str = "osm_id",
) -> str:
    """Generate HTML gallery from list of image records."""
    safe = lambda x: html.escape("" if x is None else str(x))
    cards_html = _build_cards_html(records, meta_field, meta_key)
    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<title>{safe(title)}</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif; margin: 16px; }}
h1 {{ font-size: 20px; margin: 0 0 8px 0; }}
.small {{ color:#666; font-size: 12px; margin-bottom: 12px; line-height: 1.4; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 14px; }}
.card {{ border: 1px solid #ddd; border-radius: 10px; overflow: hidden; background: #fff; }}
.card img {{ width: 100%; height: 220px; object-fit: cover; display: block; background: #f3f3f3; }}
.cap {{ padding: 10px; }}
.id {{ font-weight: 600; font-size: 14px; }}
.meta {{ font-size: 12px; color: #444; margin-top: 4px; white-space: pre-wrap; }}
.missing {{ width: 100%; height: 220px; display: flex; align-items: center; justify-content: center; background: #f3f3f3; color: #666; font-size: 12px; }}
a {{ color: inherit; text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
</style>
</head>
<body>
<h1>{safe(title)}</h1>
<div class="small">Click a thumbnail to open it in a new tab.</div>
<div class="grid">
{cards_html}
</div>
</body>
</html>"""


def main():
    ap = argparse.ArgumentParser(
        description="Build building_rankings.json and generate HTML galleries"
    )
    ap.add_argument(
        "--accepted",
        default="accepted.json",
        help="Path to accepted.json",
    )
    ap.add_argument(
        "--rejected",
        default="rejected.json",
        help="Path to rejected.json",
    )
    ap.add_argument(
        "--osm",
        default="m_out.json",
        help="Path to m_out.json or out.json (for OSM building names/tags)",
    )
    ap.add_argument(
        "--out-ranked",
        default="building_rankings.json",
        help="Output building_rankings.json",
    )
    ap.add_argument(
        "--out-sequences",
        default="sequence_rankings.json",
        help="Output sequence_rankings.json (images grouped by Mapillary sequence_id)",
    )
    ap.add_argument(
        "--out-accepted-gallery",
        default="accepted_gallery.html",
        help="Output accepted image gallery HTML",
    )
    ap.add_argument(
        "--out-rejected-gallery",
        default="rejected_gallery.html",
        help="Output rejected image gallery HTML",
    )
    ap.add_argument(
        "--no-galleries",
        action="store_true",
        help="Skip generating accepted/rejected gallery HTML",
    )
    ap.add_argument(
        "--out-sequence-gallery",
        default="accepted_by_sequence.html",
        help="Gallery with accepted images grouped by sequence (requires sequence_id in accepted.json)",
    )
    args = ap.parse_args()

    accepted_path = Path(args.accepted)
    osm_path = Path(args.osm) if Path(args.osm).exists() else None

    # Build building rankings and sequence groupings
    by_building, by_sequence = build_rankings(accepted_path, osm_path)
    out_ranked = Path(args.out_ranked)
    out_ranked.write_text(json.dumps(by_building, indent=2), encoding="utf-8")
    print(f"Wrote {out_ranked} ({len(by_building)} buildings)")

    out_sequences = Path(args.out_sequences)
    out_sequences.write_text(json.dumps(by_sequence, indent=2), encoding="utf-8")
    print(f"Wrote {out_sequences} ({len(by_sequence)} sequences)")

    if not args.no_galleries:
        # Generate accepted gallery
        accepted_data = json.loads(accepted_path.read_text(encoding="utf-8"))
        html_accepted = generate_image_gallery(
            accepted_data,
            f"Accepted images ({len(accepted_data)})",
            meta_field="best_match",
            meta_key="osm_id",
        )
        Path(args.out_accepted_gallery).write_text(html_accepted, encoding="utf-8")
        print(f"Wrote {args.out_accepted_gallery}")

        # Generate rejected gallery
        rejected_path = Path(args.rejected)
        # Sequence-grouped accepted gallery (if any images have sequence_id)
        accepted_data = json.loads(accepted_path.read_text(encoding="utf-8"))
        by_seq = {}
        for rec in accepted_data:
            seq_id = rec.get("sequence_id")
            if seq_id is not None:
                key = str(seq_id)
                if key not in by_seq:
                    by_seq[key] = []
                by_seq[key].append(rec)
        if by_seq:
            seq_sections = []
            for seq_id, recs in sorted(by_seq.items(), key=lambda x: -len(x[1])):
                grid = _build_cards_html(recs, meta_field="best_match", meta_key="osm_id")
                seq_sections.append(
                    f'<div class="seq-section">'
                    f'<h2>Sequence {html.escape(seq_id)} ({len(recs)} images)</h2>'
                    f'<div class="grid">{grid}</div></div>'
                )
            seq_gallery = f"""<!doctype html>
<html>
<head><meta charset="utf-8"/><title>Accepted by Sequence</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif; margin: 16px; }}
h1 {{ font-size: 20px; margin: 0 0 8px 0; }}
h2 {{ font-size: 16px; margin: 16px 0 8px 0; color: #333; }}
.seq-section {{ margin-bottom: 24px; border-bottom: 1px solid #eee; padding-bottom: 16px; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 14px; }}
.card {{ border: 1px solid #ddd; border-radius: 10px; overflow: hidden; background: #fff; }}
.card img {{ width: 100%; height: 220px; object-fit: cover; display: block; background: #f3f3f3; }}
.cap {{ padding: 10px; font-size: 12px; color: #444; }}
.id {{ font-weight: 600; font-size: 14px; }}
.meta {{ font-size: 12px; margin-top: 4px; }}
.missing {{ width: 100%; height: 220px; display: flex; align-items: center; justify-content: center; background: #f3f3f3; color: #666; font-size: 12px; }}
a {{ color: inherit; text-decoration: none; }}
</style>
</head>
<body>
<h1>Accepted images grouped by Mapillary sequence</h1>
{chr(10).join(seq_sections)}
</body>
</html>"""
            Path(args.out_sequence_gallery).write_text(seq_gallery, encoding="utf-8")
            print(f"Wrote {args.out_sequence_gallery} ({len(by_seq)} sequences)")

        if rejected_path.exists():
            rejected_data = json.loads(rejected_path.read_text(encoding="utf-8"))
            html_rejected = generate_image_gallery(
                rejected_data,
                f"Rejected images ({len(rejected_data)})",
                meta_field="best_candidate",
                meta_key="osm_id",
            )
            Path(args.out_rejected_gallery).write_text(html_rejected, encoding="utf-8")
            print(f"Wrote {args.out_rejected_gallery}")
        else:
            print(f"Skipped {args.out_rejected_gallery} (rejected.json not found)")

    print("\nNext: python visualize.py --ranked building_rankings.json --accepted accepted.json")


if __name__ == "__main__":
    main()
