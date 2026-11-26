"""Is there a date offset between CHIRPS and IMD?

Shifts the IMD series by -3..+3 days and reports the daily correlation with CHIRPS.
If one lag stands out (usually +-1), the products are aligned to different day
boundaries and every comparison should use that shift.

Usage: python src/lag_scan.py 1981 2025
"""
import sys
from pathlib import Path

import pandas as pd

OUT = Path(__file__).resolve().parents[1] / "data" / "processed"
RENAME = {"Pattanamtitta": "Pathanamthitta"}


def wide(path: Path) -> pd.DataFrame:
    d = pd.read_csv(path, parse_dates=["date"])
    d["district"] = d["district"].replace(RENAME)
    return d.pivot(index="date", columns="district", values="precip_mm").sort_index()


def scan(c: pd.DataFrame, i: pd.DataFrame, lags=range(-3, 4)) -> pd.DataFrame:
    rows = {}
    jjas = c.index.month.isin([6, 7, 8, 9])
    for k in lags:
        # shift(k): IMD value of day d-k is lined up with CHIRPS day d
        s = i.shift(k)
        rows[k] = {
            "all_days_median_pearson": c.corrwith(s).median(),
            "monsoon_median_pearson": c[jjas].corrwith(s[jjas]).median(),
            "monsoon_idukki": c.loc[jjas, "Idukki"].corr(s.loc[jjas, "Idukki"]),
            "monsoon_wayanad": c.loc[jjas, "Wayanad"].corr(s.loc[jjas, "Wayanad"]),
        }
    return pd.DataFrame(rows).T.round(3)


if __name__ == "__main__":
    a, b = sys.argv[1], sys.argv[2]
    c = wide(OUT / f"chirps_district_daily_{a}_{b}.csv")
    i = wide(OUT / f"imd_district_daily_{a}_{b}.csv")
    print(scan(c, i).rename_axis("imd_shift_days").to_string())
