"""At what time scale do CHIRPS and IMD agree on extremes?

For each window length k, take each product's annual maximum k-day rainfall total per
district and rank-correlate the 45 yearly values between products.
Also tests monsoon (Jun-Sep) and annual totals.

Rule of thumb for n=45 years: |Spearman| above ~0.29 is distinguishable from noise at 5%.

Usage: python src/accumulation_scan.py 1981 2025 [lag]     (use lag -1, see lag_scan.py)
"""
import sys
from pathlib import Path

import pandas as pd

OUT = Path(__file__).resolve().parents[1] / "data" / "processed"
RENAME = {"Pattanamtitta": "Pathanamthitta"}
GHATS = ["Idukki", "Wayanad", "Pathanamthitta"]
WINDOWS = [1, 2, 3, 5, 7, 10, 15, 30]


def wide(path: Path, lag: int = 0) -> pd.DataFrame:
    d = pd.read_csv(path, parse_dates=["date"])
    d["district"] = d["district"].replace(RENAME)
    d["date"] = d["date"] + pd.Timedelta(days=lag)
    return d.pivot(index="date", columns="district", values="precip_mm").sort_index()


def annual_max_k(w: pd.DataFrame, k: int) -> pd.DataFrame:
    roll = w.rolling(k, min_periods=k).sum()
    return roll.groupby(roll.index.year).max()


def scan(c: pd.DataFrame, i: pd.DataFrame) -> pd.DataFrame:
    idx = c.index.intersection(i.index)
    c, i = c.loc[idx], i.loc[idx]
    rows = {}
    for k in WINDOWS:
        ac, ai = annual_max_k(c, k), annual_max_k(i, k)
        r = ac.corrwith(ai, method="spearman")
        rows[f"annual max {k}-day"] = {
            "median_all_districts": r.median(), **{g: r[g] for g in GHATS},
            "min": r.min(), "max": r.max(),
            "ratio_chirps/imd": (ac.mean() / ai.mean()).median()}
    for name, sel in [("monsoon Jun-Sep total", [6, 7, 8, 9]), ("annual total", list(range(1, 13)))]:
        tc = c[c.index.month.isin(sel)].groupby(c[c.index.month.isin(sel)].index.year).sum()
        ti = i[i.index.month.isin(sel)].groupby(i[i.index.month.isin(sel)].index.year).sum()
        r = tc.corrwith(ti, method="spearman")
        rows[name] = {"median_all_districts": r.median(), **{g: r[g] for g in GHATS},
                      "min": r.min(), "max": r.max(),
                      "ratio_chirps/imd": (tc.mean() / ti.mean()).median()}
    return pd.DataFrame(rows).T.round(2)


if __name__ == "__main__":
    a, b = sys.argv[1], sys.argv[2]
    lag = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    c = wide(OUT / f"chirps_district_daily_{a}_{b}.csv")
    i = wide(OUT / f"imd_district_daily_{a}_{b}.csv", lag)
    print(f"lag = {lag}")
    res = scan(c, i)
    pd.set_option("display.width", 220)
    print(res.to_string())
    res.to_csv(OUT / "accumulation_agreement.csv")
