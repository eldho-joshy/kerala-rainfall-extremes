"""Download daily CHIRPS v2 rainfall for a Kerala bounding box, one NetCDF per year.

Source: NOAA ERDDAP mirror of CHIRPS v2.0 (0.05 deg, daily, 1981-present).
Raw files go to data/raw/ and are never edited by hand.

Usage:
    python src/fetch_chirps.py 1981 2025
"""
import sys
import time
from pathlib import Path

import requests

BASE = "https://coastwatch.pfeg.noaa.gov/erddap/griddap/chirps20GlobalDailyP05.nc"
# Kerala bounding box (slightly padded). We clip to real district polygons later,
# the box is only to keep downloads small.
LAT = (8.0, 13.0)
LON = (74.5, 77.5)
RAW = Path(__file__).resolve().parents[1] / "data" / "raw"


def url_for(year: int) -> str:
    t0, t1 = f"{year}-01-01T00:00:00Z", f"{year}-12-31T00:00:00Z"
    return (
        f"{BASE}?precip[({t0}):1:({t1})]"
        f"[({LAT[0]}):1:({LAT[1]})][({LON[0]}):1:({LON[1]})]"
    )


def fetch_year(year: int, retries: int = 3) -> None:
    out = RAW / f"chirps_kerala_{year}.nc"
    if out.exists() and out.stat().st_size > 0:
        print(f"{year}: already have it, skipping")
        return
    for attempt in range(1, retries + 1):
        try:
            with requests.get(url_for(year), stream=True, timeout=300) as r:
                r.raise_for_status()
                tmp = out.with_suffix(".part")
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(1 << 20):
                        f.write(chunk)
                tmp.rename(out)
            print(f"{year}: saved {out.name} ({out.stat().st_size/1e6:.1f} MB)")
            return
        except requests.RequestException as e:
            print(f"{year}: attempt {attempt} failed: {e}")
            time.sleep(5 * attempt)
    print(f"{year}: GAVE UP, rerun later")


if __name__ == "__main__":
    start, end = int(sys.argv[1]), int(sys.argv[2])
    RAW.mkdir(parents=True, exist_ok=True)
    for y in range(start, end + 1):
        fetch_year(y)
