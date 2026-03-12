# get buildings and nearby mapillary images
import json
import os
import time
import requests
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root (same dir as this script) or current directory
script_dir = Path(__file__).resolve().parent
load_dotenv(script_dir / ".env")
load_dotenv()  # fallback: load from current working directory

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
MAPILLARY_URL = "https://graph.mapillary.com/images"


COORDS = [
    #(42.2754250, -83.7432138), # central
    #(42.292091, -83.716011), # north
    (42.274933, -83.743182), # munger
    
]

BUFFER_DEG = 0.01  # ~1000m-ish

OUT_FILE = "m_out.json"   # set to None to print instead of save

MAPILLARY_ACCESS_TOKEN = os.environ.get("MAPILLARY_ACCESS_TOKEN") or None

# ============================================================


def bbox_from_center(lat, lon, buffer_deg):
    # returns (south, west, north, east)
    return (lat - buffer_deg, lon - buffer_deg,
            lat + buffer_deg, lon + buffer_deg)


def overpass_query(bbox):
    s, w, n, e = bbox
    return f"""
[out:json][timeout:25];
(
  way["building"]({s},{w},{n},{e});
  relation["building"]({s},{w},{n},{e});
);
out body;
>;
out skel qt;
"""


def fetch_osm(bbox):
    r = requests.post(
        OVERPASS_URL,
        data={"data": overpass_query(bbox)},
        timeout=60
    )
    r.raise_for_status()
    return r.json()


def fetch_mapillary(bbox, token, limit=200):
    s, w, n, e = bbox
    bbox_str = f"{w},{s},{e},{n}"  # Mapillary expects west,south,east,north

    params = {
        "bbox": bbox_str,
        "fields": "id,thumb_original_url,computed_geometry,computed_compass_angle,captured_at,sequence",
        "access_token": token,
        "limit": limit,
    }

    r = requests.get(MAPILLARY_URL, params=params, timeout=30)
    r.raise_for_status()
    return r.json().get("data", [])


def main():
    if not MAPILLARY_ACCESS_TOKEN:
        print("Error: MAPILLARY_ACCESS_TOKEN is required. Set it in .env or export it.")
        raise SystemExit(1)

    results = []
    for (lat, lon) in COORDS:
        bbox = bbox_from_center(lat, lon, BUFFER_DEG)

        record = {
            "coordinate": {"lat": lat, "lon": lon},
            "bbox_south_west_north_east": bbox,
            "osm_raw": fetch_osm(bbox),
            "mapillary": fetch_mapillary(bbox, MAPILLARY_ACCESS_TOKEN),
        }

        results.append(record)
        time.sleep(0.25)  # be polite to APIs

    output_json = json.dumps(results, indent=2)

    if OUT_FILE:
        with open(OUT_FILE, "w") as f:
            f.write(output_json)
        print(f"Saved {OUT_FILE}")
    else:
        print(output_json)


if __name__ == "__main__":
    main()