"""Export simplified Kerala district polygons (FAO GAUL 2015 via Earth Engine) as GeoJSON for the map.

Usage: python src/export_boundaries.py --project YOUR_CLOUD_PROJECT_ID
Writes docs/data/kerala_districts.geojson
Note: GAUL 2015 is deprecated and its Idukki/Ernakulam boundary looks shifted; the map must say so.
"""
import argparse
import json
from pathlib import Path

import ee

DOCS = Path(__file__).resolve().parents[1] / "docs" / "data"
RENAME = {"Pattanamtitta": "Pathanamthitta"}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    a = ap.parse_args()
    ee.Initialize(project=a.project)
    fc = (ee.FeatureCollection("FAO/GAUL/2015/level2")
          .filter(ee.Filter.eq("ADM1_NAME", "Kerala")))
    fc = fc.map(lambda f: ee.Feature(f.geometry().simplify(500),
                                     {"name": f.get("ADM2_NAME"),
                                      "area_km2": f.geometry().area(1).divide(1e6)}))
    gj = fc.getInfo()
    for f in gj["features"]:
        f["properties"]["name"] = RENAME.get(f["properties"]["name"], f["properties"]["name"])
        f["properties"]["area_km2"] = round(f["properties"]["area_km2"])
        f.pop("id", None)
    assert len(gj["features"]) == 14, f"expected 14 districts, got {len(gj['features'])}"
    DOCS.mkdir(parents=True, exist_ok=True)
    out = DOCS / "kerala_districts.geojson"
    out.write_text(json.dumps(gj))
    print(f"Wrote {out} ({out.stat().st_size/1e3:.0f} kB, {len(gj['features'])} districts)")
