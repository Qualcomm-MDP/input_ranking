# Input Ranking

Pipeline for ranking street-level Mapillary images by building match, with optional scene recognition and segmentation.

## Project structure

```
input_ranking/
├── data/                    # JSON data (input & output)
│   ├── m_out.json          # Raw OSM + Mapillary fetch
│   ├── accepted.json       # Filtered images
│   ├── rejected.json
│   ├── building_rankings.json
│   ├── sequence_rankings.json
│   └── accepted_with_analysis.json
├── output/
│   ├── thumbnails/         # Downloaded images (gitignored)
│   ├── scene_scores/       # ResNet Places365 results
│   ├── segmentation/       # Mask2Former results
│   └── galleries/          # HTML galleries
├── models/
│   └── places365/          # ResNet weights (download separately)
├── *.py                    # Scripts
├── .env                    # MAPILLARY_ACCESS_TOKEN (gitignored)
└── requirements.txt
```

## Pipeline

1. **Fetch data**: `python get_mapillary.py` → `data/m_out.json`
2. **Filter**: `python filter_metadata.py` → `data/accepted.json`, `data/rejected.json`
3. **Rank**: `python build_rankings.py` → `data/building_rankings.json`, galleries
4. **Analyze**: `python run_analysis.py` → `data/accepted_with_analysis.json`
5. **Gallery**: `python generate_analysis_gallery.py` → `output/galleries/`
6. **Visualize**: `python visualize.py` → `output/galleries/building_gallery.html`

## Setup

- Add `MAPILLARY_ACCESS_TOKEN` to `.env`
- Place `resnet18_places365.pth.tar` in `models/places365/` for scene recognition
