#!/usr/bin/env python3
"""
Orchestrate: download thumbnails -> scene recognition (ResNet/Places365) -> segmentation (Mask2Former).
Merge results back into accepted.json as accepted_with_analysis.json.
Scene recognition rejects images with top label in SCENE_REJECT_LABELS (e.g. car interior, indoor).
"""
import argparse
import json
from pathlib import Path

from download_thumbnails import download

# Scene labels that indicate "not useful for street-level building views" - reject these
SCENE_REJECT_LABELS = {
    "car_interior",
    "bus_interior",
    "train_interior",
    "cockpit",
    "bedroom",
    "living_room",
    "bathroom",
    "kitchen",
    "dining_room",
    "nursery",
    "closet",
    "shower",
    "home_office",
    "home_theater",
    "television_room",
    "childs_room",
    "dorm_room",
    "bedchamber",
    "hospital_room",
    "operating_room",
    "jail_cell",
    "elevator/door",
    "elevator_lobby",
    "elevator_shaft",
    "subway_station/platform",
    "train_station/platform",
}
from scene_recognition import run_scene_recognition
from segmentation import run_segmentation


def merge_into_accepted(
    accepted_path: Path,
    scene_results: dict,
    seg_results: dict,
    out_path: Path,
) -> None:
    """Add scene and segmentation fields to each accepted image record."""
    data = json.loads(accepted_path.read_text(encoding="utf-8"))

    for rec in data:
        img_id = str(rec.get("id", ""))
        if not img_id:
            continue

        if img_id in scene_results:
            rec["scene_top5"] = scene_results[img_id]
            top1 = scene_results[img_id][0] if scene_results[img_id] else None
            rec["scene_top1"] = top1
            # Reject if top scene is car interior, indoor domestic, etc.
            if top1:
                label = (top1.get("label") or "").lower().strip()
                if label in SCENE_REJECT_LABELS:
                    rec["scene_reject"] = True
                    rec["scene_reject_reason"] = f"scene_{label}"
                else:
                    rec["scene_reject"] = False
                    rec["scene_reject_reason"] = None
            else:
                rec["scene_reject"] = False
                rec["scene_reject_reason"] = None
        else:
            rec["scene_top5"] = []
            rec["scene_top1"] = None
            rec["scene_reject"] = False
            rec["scene_reject_reason"] = None

        if img_id in seg_results:
            s = seg_results[img_id]
            rec["segmentation"] = {
                "building_frac": s["building_frac"],
                "veg_over_building": s["veg_over_building"],
                "reject": s["reject"],
                "reason": s["reason"],
            }
        else:
            rec["segmentation"] = None

    out_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    n_scene_reject = sum(1 for r in data if r.get("scene_reject"))
    print(f"Wrote {out_path}")
    if n_scene_reject:
        print(f"  Scene rejected (car interior, indoor, etc.): {n_scene_reject}")


def main():
    ap = argparse.ArgumentParser(
        description="Download thumbnails, run scene recognition and segmentation, merge into accepted"
    )
    ap.add_argument("--accepted", default="data/accepted.json", help="Path to accepted.json")
    ap.add_argument("--thumbnails", default="output/thumbnails", help="Directory for downloaded images")
    ap.add_argument("--scene-out", default="output/scene_scores", help="Scene recognition output")
    ap.add_argument("--seg-out", default="output/segmentation", help="Segmentation output")
    ap.add_argument("--out", default="data/accepted_with_analysis.json", help="Merged output JSON")
    ap.add_argument(
        "--out-filtered",
        default=None,
        help="Optional: write filtered JSON (excludes scene-rejected and seg-rejected)",
    )
    ap.add_argument("--skip-download", action="store_true", help="Skip download (use existing thumbnails)")
    ap.add_argument("--skip-scene", action="store_true", help="Skip scene recognition")
    ap.add_argument("--skip-segmentation", action="store_true", help="Skip segmentation")
    ap.add_argument("--device", default="cpu", help="Device for scene: cpu, cuda, mps")
    ap.add_argument("--seg-device", type=int, default=-1, help="Segmentation: -1 CPU, 0 GPU")
    args = ap.parse_args()

    accepted_path = Path(args.accepted)
    thumb_dir = Path(args.thumbnails)

    if not args.skip_download:
        download(accepted_path, thumb_dir)
    else:
        thumb_dir.mkdir(parents=True, exist_ok=True)

    scene_results = {}
    if not args.skip_scene:
        scene_results = run_scene_recognition(
            thumb_dir,
            Path(args.scene_out),
            device=args.device,
        )

    seg_results = {}
    if not args.skip_segmentation:
        seg_results = run_segmentation(
            thumb_dir,
            Path(args.seg_out),
            device=args.seg_device,
        )

    merge_into_accepted(
        accepted_path,
        scene_results,
        seg_results,
        Path(args.out),
    )

    if args.out_filtered:
        data = json.loads(Path(args.out).read_text(encoding="utf-8"))
        filtered = [
            r for r in data
            if not r.get("scene_reject") and not (r.get("segmentation") or {}).get("reject")
        ]
        Path(args.out_filtered).write_text(json.dumps(filtered, indent=2), encoding="utf-8")
        print(f"Wrote {args.out_filtered} ({len(filtered)} images, excluded {len(data) - len(filtered)})")


if __name__ == "__main__":
    main()
