#!/usr/bin/env python3
"""
Mask2Former panoptic segmentation. Scores building fraction and vegetation
occlusion per image. Integrates with pipeline via image_id filenames.
"""
import argparse
import csv
import logging
import math
from dataclasses import dataclass
from pathlib import Path

# Suppress Mask2Former "label_ids_to_fuse unset" message (prints per image)
logging.getLogger("transformers.models.mask2former").setLevel(logging.ERROR)

import cv2
import numpy as np
from PIL import Image
from transformers import pipeline

MODEL_ID = "facebook/mask2former-swin-large-cityscapes-panoptic"
MIN_BUILDING_FRAC = 0.08
USE_VEG_OCCLUSION = True
MAX_VEG_OVER_BUILDING = 0.25
BUILDING_COLOR_BGR = (0, 255, 0)
ALPHA = 0.35
THUMB_W = 480
FONT = cv2.FONT_HERSHEY_SIMPLEX


@dataclass
class SemScore:
    path: str
    image_id: str
    building_frac: float
    veg_over_building: float | None
    reject: bool
    reason: str


def to_np_mask(seg_mask):
    if isinstance(seg_mask, Image.Image):
        m = np.array(seg_mask)
    else:
        m = np.array(seg_mask)
    if m.ndim == 3:
        m = m[..., 0]
    return m > 0


def union_masks(segments, label_name: str, h: int, w: int) -> np.ndarray:
    out = np.zeros((h, w), dtype=bool)
    want = label_name.lower()
    for seg in segments:
        label = str(seg.get("label", "")).lower()
        if label == want:
            out |= to_np_mask(seg["mask"])
    return out


def compute_scores(building_mask: np.ndarray, veg_mask: np.ndarray | None):
    h, w = building_mask.shape
    total = float(h * w)
    bldg_area = float(building_mask.sum())
    building_frac = bldg_area / total

    veg_over_building = None
    if veg_mask is not None and bldg_area > 0:
        veg_over_building = float((veg_mask & building_mask).sum()) / bldg_area

    if building_frac < MIN_BUILDING_FRAC:
        return building_frac, veg_over_building, True, "low_building"
    if building_frac > 0.93:
        return building_frac, veg_over_building, True, "likely_interior"

    if USE_VEG_OCCLUSION and veg_over_building is not None:
        if veg_over_building > MAX_VEG_OVER_BUILDING:
            return building_frac, veg_over_building, True, "veg_occluding_building"

    return building_frac, veg_over_building, False, "ok"


def overlay_mask(bgr: np.ndarray, mask: np.ndarray, color_bgr, alpha: float):
    out = bgr.copy()
    color_img = np.zeros_like(out, dtype=np.uint8)
    color_img[:] = color_bgr
    out[mask] = (alpha * color_img[mask] + (1 - alpha) * out[mask]).astype(np.uint8)
    return out


def draw_label(img_bgr, s: SemScore):
    out = img_bgr.copy()
    h, w = out.shape[:2]
    overlay_h = int(0.22 * h)
    cv2.rectangle(out, (0, 0), (w, overlay_h), (0, 0, 0), thickness=-1)
    a = 0.55
    out[:overlay_h] = cv2.addWeighted(out[:overlay_h], a, img_bgr[:overlay_h], 1 - a, 0)

    status = "REJECT" if s.reject else "KEEP"
    line2 = f"bldg={s.building_frac:.2f}"
    if s.veg_over_building is not None:
        line2 += f"  veg∩bldg={s.veg_over_building:.2f}"

    for i, text in enumerate([f"{status} ({s.reason})", line2, s.image_id]):
        cv2.putText(out, text, (10, 22 + i * 22), FONT, 0.65, (255, 255, 255), 2, cv2.LINE_AA)
    return out


def make_contact_sheet(items, out_path, cols=4, thumb_w=THUMB_W):
    thumbs = [img for (_, img) in items]
    if not thumbs:
        return
    rows = int(math.ceil(len(thumbs) / cols))
    max_h = max(t.shape[0] for t in thumbs)
    pad = 10
    sheet_w = cols * thumb_w + (cols + 1) * pad
    sheet_h = rows * max_h + (rows + 1) * pad
    sheet = np.full((sheet_h, sheet_w, 3), 255, dtype=np.uint8)
    for idx, thumb in enumerate(thumbs):
        r, c = idx // cols, idx % cols
        x0, y0 = pad + c * (thumb_w + pad), pad + r * (max_h + pad)
        hh, ww = thumb.shape[:2]
        sheet[y0 : y0 + hh, x0 : x0 + ww] = thumb
    cv2.imwrite(str(out_path), sheet)


def run_segmentation(
    in_dir: Path,
    out_dir: Path,
    device: int = -1,
) -> dict:
    """
    Run Mask2Former segmentation on all images.
    Returns dict: {image_id: {"building_frac": float, "veg_over_building": float|None, "reject": bool, "reason": str}}
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    seg = pipeline("image-segmentation", model=MODEL_ID, device=device)

    exts = ("*.jpg", "*.jpeg", "*.png", "*.JPG", "*.JPEG", "*.PNG")
    paths = []
    for e in exts:
        paths.extend(in_dir.glob(e))
    paths = sorted(paths)
    if not paths:
        return {}

    results = {}
    scored: list[SemScore] = []
    thumbs: list[tuple[SemScore, np.ndarray]] = []

    for p in paths:
        bgr = cv2.imread(str(p))
        if bgr is None:
            continue
        h, w = bgr.shape[:2]
        image_id = p.stem

        pil = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
        segments = seg(pil)

        building_mask = union_masks(segments, "building", h, w)
        veg_mask = union_masks(segments, "vegetation", h, w) if USE_VEG_OCCLUSION else None
        building_frac, veg_over_building, reject, reason = compute_scores(building_mask, veg_mask)

        s = SemScore(
            path=str(p),
            image_id=image_id,
            building_frac=building_frac,
            veg_over_building=veg_over_building,
            reject=reject,
            reason=reason,
        )
        scored.append(s)
        results[image_id] = {
            "building_frac": building_frac,
            "veg_over_building": veg_over_building,
            "reject": reject,
            "reason": reason,
        }

        scale = THUMB_W / float(w)
        new_h = int(round(h * scale))
        thumb = cv2.resize(bgr, (THUMB_W, new_h), interpolation=cv2.INTER_AREA)
        bmask_thumb = cv2.resize(
            building_mask.astype(np.uint8), (THUMB_W, new_h), interpolation=cv2.INTER_NEAREST
        ).astype(bool)
        thumb = overlay_mask(thumb, bmask_thumb, BUILDING_COLOR_BGR, ALPHA)
        thumb = draw_label(thumb, s)
        thumbs.append((s, thumb))

        print(p.name, f"bldg={building_frac:.2f}", "->", reason)

    scored.sort(key=lambda s: (not s.reject, s.building_frac))
    thumb_map = {ss.image_id: img for (ss, img) in thumbs}
    ordered_thumbs = [(s, thumb_map[s.image_id]) for s in scored if s.image_id in thumb_map]

    csv_path = out_dir / "semantic_scores.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["image_id", "path", "reject", "reason", "building_frac", "veg_over_building"])
        for s in scored:
            w.writerow([
                s.image_id, s.path, int(s.reject), s.reason,
                f"{s.building_frac:.4f}",
                "" if s.veg_over_building is None else f"{s.veg_over_building:.4f}",
            ])

    make_contact_sheet(ordered_thumbs, out_dir / "semantic_contact_sheet.jpg")
    print(f"Wrote {csv_path}")
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="thumbnails", help="Directory with images")
    ap.add_argument("--output", default="out_segmentation", help="Output directory")
    ap.add_argument("--device", type=int, default=-1, help="-1 for CPU, 0 for GPU")
    args = ap.parse_args()
    run_segmentation(Path(args.input), Path(args.output), device=args.device)


if __name__ == "__main__":
    main()
