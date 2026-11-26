"""Export daily district-mean IMD gridded rainfall (0.25 deg) for Kerala.

Output: data/processed/imd_district_daily_<start>_<end>.csv
Columns: date, district, precip_mm   (same layout as the CHIRPS export)

Usage:
    pip install imdlib
    python src/export_imd.py 1981 2025

Resumable: raw yearly .grd files go to data/raw/imd/rain/ (gitignored) and each
year's district table is cached in data/processed/imd_parts/.
IMD may not have the latest year yet; if a year fails, rerun with an earlier end year.
"""
import sys
from datetime import date
from pathlib import Path

import imdlib as imd
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
IMD_DIR = ROOT / "data" / "raw" / "imd"
OUT = ROOT / "data" / "processed"
PARTS = OUT / "imd_parts"
N_DISTRICTS = 14


def year_table(y: int) -> pd.DataFrame:
    part = PARTS / f"{y}.csv"
    if part.exists():
        return pd.read_csv(part)

    grd = IMD_DIR / "rain" / f"{y}.grd"
    if grd.exists():
        data = imd.open_data("rain", y, y, "yearwise", str(IMD_DIR))
    else:
        data = imd.get_data("rain", y, y, fn_format="yearwise", file_dir=str(IMD_DIR))

    wide = data.region(state="Kerala", by="district")     # area-weighted district means
    wide.index.name = "date"
    long = (wide.rename(columns=lambda c: str(c).split(" (")[0])
                .reset_index()
                .melt(id_vars="date", var_name="district", value_name="precip_mm"))
    long["date"] = pd.to_datetime(long["date"]).dt.strftime("%Y-%m-%d")

    days = (date(y + 1, 1, 1) - date(y, 1, 1)).days
    if long["district"].nunique() != N_DISTRICTS or len(long) != days * N_DISTRICTS:
        raise SystemExit(f"{y}: got {long['district'].nunique()} districts / {len(long)} rows, "
                         f"expected {N_DISTRICTS} / {days * N_DISTRICTS}. Not saving.")
    long.to_csv(part, index=False)
    return long


if __name__ == "__main__":
    start, end = int(sys.argv[1]), int(sys.argv[2])
    IMD_DIR.mkdir(parents=True, exist_ok=True)
    PARTS.mkdir(parents=True, exist_ok=True)
    frames = []
    for y in range(start, end + 1):
        df = year_table(y)
        print(f"{y}: {len(df)} rows, NaNs: {df['precip_mm'].isna().sum()}")
        frames.append(df)
    full = pd.concat(frames).sort_values(["district", "date"])
    out = OUT / f"imd_district_daily_{start}_{end}.csv"
    full.to_csv(out, index=False)
    print(f"Wrote {out} ({len(full)} rows)")
