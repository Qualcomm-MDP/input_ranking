#!/usr/bin/env python3
"""
ResNet18 Places365 scene recognition. Reads images from a directory,
outputs CSV with top-k scene labels per image. Integrates with pipeline
via image_id filenames (e.g. 12345.jpg).
"""
import argparse
import glob
import json
import math
import os
from pathlib import Path
from typing import List, Tuple

import cv2
import numpy as np
import torch
from PIL import Image
from torchvision import transforms
from torchvision.models import resnet18

SCRIPT_DIR = Path(__file__).resolve().parent
PLACES_DIR = SCRIPT_DIR / "places365"
WEIGHTS_PATH = PLACES_DIR / "resnet18_places365.pth.tar"
CATS_PATH = PLACES_DIR / "categories_places365.txt"

TOPK = 5
THUMB_W = 480
COLS = 4
FONT = cv2.FONT_HERSHEY_SIMPLEX


def load_categories(path: Path) -> List[str]:
    classes = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            cat = None
            for p in parts:
                if "/" in p:
                    cat = p
                    break
            if cat is None:
                cat = parts[-1]
            cat = cat.replace("\\", "/")
            if cat.startswith("/"):
                cat = cat[1:]
            if len(cat) >= 2 and cat[1] == "/":
                cat = cat[2:]
            classes.append(cat)
    return classes


def load_places365_model(weights_path: Path, device: str = "cpu"):
    model = resnet18(num_classes=365)
    ckpt = torch.load(str(weights_path), map_location=device)

    state_dict = ckpt.get("state_dict", ckpt)
    cleaned = {}
    for k, v in state_dict.items():
        nk = k.replace("module.", "")
        cleaned[nk] = v

    model.load_state_dict(cleaned, strict=True)
    model.eval()
    model.to(device)

    tfm = transforms.Compose([
        transforms.Resize((256, 256)),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])
    return model, tfm


def list_images(in_dir: Path) -> List[Path]:
    exts = ("*.jpg", "*.jpeg", "*.png", "*.JPG", "*.JPEG", "*.PNG", "*.webp", "*.WEBP")
    paths = []
    for e in exts:
        paths.extend(in_dir.glob(e))
    return sorted(paths, key=lambda p: str(p))


def classify_image(model, tfm, classes: List[str], img_path: Path, device: str, topk: int) -> List[Tuple[str, float]]:
    img = Image.open(img_path).convert("RGB")
    x = tfm(img).unsqueeze(0).to(device)
    with torch.no_grad():
        logits = model(x)
        probs = torch.softmax(logits, dim=1)[0]
        vals, idxs = torch.topk(probs, k=topk)
    return [(classes[i], float(v)) for v, i in zip(vals.tolist(), idxs.tolist())]


def run_scene_recognition(
    in_dir: Path,
    out_dir: Path,
    device: str = "cpu",
    topk: int = TOPK,
) -> dict:
    """
    Run scene recognition on all images in in_dir.
    Returns dict: {image_id: [{"label": str, "prob": float}, ...]}
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    if not WEIGHTS_PATH.exists():
        raise FileNotFoundError(
            f"Missing ResNet weights: {WEIGHTS_PATH}\n"
            "Place resnet18_places365.pth.tar in places365/ (no decompression needed)"
        )
    if not CATS_PATH.exists():
        raise FileNotFoundError(f"Missing categories: {CATS_PATH}")

    classes = load_categories(CATS_PATH)
    model, tfm = load_places365_model(WEIGHTS_PATH, device=device)

    paths = list_images(in_dir)
    if not paths:
        return {}

    results = {}
    csv_path = out_dir / "scene_scores.csv"

    with open(csv_path, "w", newline="") as f:
        import csv
        w = csv.writer(f)
        w.writerow(["image_id", "path"] + [f"label_{i+1}" for i in range(topk)] + [f"prob_{i+1}" for i in range(topk)])

        for p in paths:
            image_id = p.stem
            try:
                preds = classify_image(model, tfm, classes, p, device, topk)
            except Exception as e:
                print(f"Failed {p.name}: {e}")
                continue

            results[image_id] = [{"label": lbl, "prob": prob} for lbl, prob in preds]
            row = [image_id, str(p)] + [lbl for lbl, _ in preds] + [f"{prob:.6f}" for _, prob in preds]
            w.writerow(row)
            print(p.name, "->", preds[0][0], f"{preds[0][1]:.2f}")

    print(f"Wrote {csv_path}")
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="thumbnails", help="Directory with images (e.g. from download_thumbnails)")
    ap.add_argument("--output", default="out_scene_scores", help="Output directory for CSV")
    ap.add_argument("--device", default="cpu", help="cpu, cuda, or mps")
    ap.add_argument("--topk", type=int, default=5)
    args = ap.parse_args()
    run_scene_recognition(
        Path(args.input),
        Path(args.output),
        device=args.device,
        topk=args.topk,
    )


if __name__ == "__main__":
    main()
