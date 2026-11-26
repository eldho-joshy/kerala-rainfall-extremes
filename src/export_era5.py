"""Export daily district-mean ERA5-Land rainfall for Kerala via Google Earth Engine.

Output: data/processed/era5land_district_daily_<start>_<end>.csv
ERA5-Land is a reanalysis (0.1 deg, ~11 km), not an observation: it is a third, independent-ish
opinion, not ground truth. Daily total = UTC day, like CHIRPS. Band is in metres, converted to mm.
Columns: date, district, precip_mm   (one row per district per day)

Setup (once):
    pip install earthengine-api pandas
    earthengine authenticate          # opens browser, sign in
Usage:
    python src/export_era5.py --project YOUR_CLOUD_PROJECT_ID 2018 2018   # test run
    python src/export_era5.py --project YOUR_CLOUD_PROJECT_ID 1981 2025   # full run

Resumable: each half-year is cached in data/processed/parts_era5/ and skipped if present.
"""
import argparse
import time
from datetime import date
from pathlib import Path

import ee
import pandas as pd

OUT = Path(__file__).resolve().parents[1] / "data" / "processed"
PARTS = OUT / "parts_era5"
N_DISTRICTS = 14


def get_districts():
    fc = (ee.FeatureCollection("FAO/GAUL/2015/level2")
          .filter(ee.Filter.eq("ADM1_NAME", "Kerala")))
    names = sorted(fc.aggregate_array("ADM2_NAME").getInfo())
    print(f"Found {len(names)} districts: {names}")
    if len(names) != N_DISTRICTS:
        raise SystemExit(f"Expected {N_DISTRICTS} districts, got {len(names)}. "
                         "Boundary source is off: record this in the README audit and investigate.")
    return fc


def fetch_chunk(districts, start: str, end: str, retries: int = 4) -> pd.DataFrame:
    chirps = (ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR")
              .filterDate(start, end).select("total_precipitation_sum"))

    def per_image(img):
        d = img.date().format("YYYY-MM-dd")
        img = img.multiply(1000)  # metres -> mm
        stats = img.reduceRegions(collection=districts,
                                  reducer=ee.Reducer.mean(), scale=11132)
        return stats.map(lambda f: ee.Feature(None, {
            "date": d, "district": f.get("ADM2_NAME"), "precip_mm": f.get("mean")}))

    fc = chirps.map(per_image).flatten()
    for attempt in range(1, retries + 1):
        try:
            feats = fc.getInfo()["features"]
            return pd.DataFrame([f["properties"] for f in feats])
        except Exception as e:  # noqa: BLE001  (EE raises many error types)
            print(f"  {start}..{end} attempt {attempt} failed: {e}")
            time.sleep(10 * attempt)
    raise SystemExit(f"Giving up on {start}..{end}; rerun to resume.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("start_year", type=int)
    ap.add_argument("end_year", type=int)
    a = ap.parse_args()

    ee.Initialize(project=a.project)
    PARTS.mkdir(parents=True, exist_ok=True)
    districts = get_districts()

    frames = []
    for y in range(a.start_year, a.end_year + 1):
        for (s, e) in [(f"{y}-01-01", f"{y}-07-01"), (f"{y}-07-01", f"{y+1}-01-01")]:
            part = PARTS / f"{s}_{e}.csv"
            if part.exists():
                df = pd.read_csv(part)
            else:
                df = fetch_chunk(districts, s, e)
                days = (date.fromisoformat(e) - date.fromisoformat(s)).days
                if len(df) != days * N_DISTRICTS:
                    raise SystemExit(f"{s}..{e}: got {len(df)} rows, expected "
                                     f"{days * N_DISTRICTS}. Not saving a bad chunk.")
                df.to_csv(part, index=False)
            print(f"{s}..{e}: {len(df)} rows ok")
            frames.append(df)

    full = pd.concat(frames).sort_values(["district", "date"])
    out = OUT / f"era5land_district_daily_{a.start_year}_{a.end_year}.csv"
    full.to_csv(out, index=False)
    print(f"Wrote {out} ({len(full)} rows, NaNs: {full['precip_mm'].isna().sum()})")


if __name__ == "__main__":
    main()
