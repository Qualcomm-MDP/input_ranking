#!/usr/bin/env python3
"""
Download thumbnails for accepted images from accepted.json.
Saves as {image_id}.jpg so results can be traced back.
"""
import argparse
import json
import time
from pathlib import Path

import requests


def download(accepted_path: str | Path, out_dir: str | Path, delay: float = 0.1) -> int:
    """Download thumbnails. Returns count of newly downloaded images."""
    data = json.loads(Path(accepted_path).read_text(encoding="utf-8"))
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    downloaded = 0
    skipped = 0
    failed = 0

    for rec in data:
        img_id = rec.get("id")
        url = rec.get("thumb_original_url")
        if not img_id or not url or not url.startswith("http"):
            skipped += 1
            continue

        out_path = out_dir / f"{img_id}.jpg"
        if out_path.exists():
            skipped += 1
            continue

        try:
            r = requests.get(url, timeout=30, stream=True)
            r.raise_for_status()
            out_path.write_bytes(r.content)
            downloaded += 1
            print(f"Downloaded {img_id}")
        except Exception as e:
            failed += 1
            print(f"Failed {img_id}: {e}")

        time.sleep(delay)

    print(f"Done: {downloaded} downloaded, {skipped} skipped, {failed} failed")
    print(f"Images in {out_dir.resolve()}")
    return downloaded


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--accepted", default="data/accepted.json", help="Path to accepted.json")
    ap.add_argument("--out-dir", default="output/thumbnails", help="Output directory")
    ap.add_argument("--delay", type=float, default=0.1, help="Delay between requests (seconds)")
    args = ap.parse_args()
    download(args.accepted, args.out_dir, args.delay)


if __name__ == "__main__":
    main()
