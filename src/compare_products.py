"""How well do CHIRPS and IMD agree, district by district?

Totals can be biased and still be useful; what matters for an extremes analysis is
whether the two products agree on WHEN heavy rain happens and how annual maxima
move from year to year.

Usage:
    python src/compare_products.py 1981 2025 [lag]
lag k pairs CHIRPS day d with IMD day d-k. From lag_scan.py the best value is -1
(CHIRPS day d overlaps IMD day d+1 most), so run: python src/compare_products.py 1981 2025 -1
Reads  data/processed/chirps_district_daily_<a>_<b>.csv and imd_district_daily_<a>_<b>.csv
Writes data/processed/product_agreement.csv
"""
import sys
from pathlib import Path

import pandas as pd

OUT = Path(__file__).resolve().parents[1] / "data" / "processed"
RENAME = {"Pattanamtitta": "Pathanamthitta"}   # GAUL spelling -> standard


def load(path: Path, name: str) -> pd.DataFrame:
    d = pd.read_csv(path, parse_dates=["date"])
    d["district"] = d["district"].replace(RENAME)
    return d.rename(columns={"precip_mm": name})


def agreement(m: pd.DataFrame) -> dict:
    """m: one district, columns date, chirps, imd."""
    m = m.dropna(subset=["chirps", "imd"])
    yr = m["date"].dt.year
    ann = m.groupby(yr)[["chirps", "imd"]].max()                    # annual max daily rainfall
    jjas = m[m["date"].dt.month.isin([6, 7, 8, 9])]
    tot = jjas.groupby(jjas["date"].dt.year)[["chirps", "imd"]].sum()  # monsoon totals
    # heavy days: each product's own 99th percentile of rainy days (>=2.5 mm)
    thr = {k: m.loc[m[k] >= 2.5, k].quantile(0.99) for k in ("chirps", "imd")}
    hc, hi = m["chirps"] >= thr["chirps"], m["imd"] >= thr["imd"]
    # allow +-1 day so a timing shift (UTC vs IST day boundary) is not counted as a miss
    hi_near = hi | hi.shift(1, fill_value=False) | hi.shift(-1, fill_value=False)
    return {
        "daily_pearson": m["chirps"].corr(m["imd"]),
        "daily_spearman": m["chirps"].corr(m["imd"], method="spearman"),
        "annual_max_spearman": ann["chirps"].corr(ann["imd"], method="spearman"),
        "annual_max_ratio_chirps/imd": ann["chirps"].mean() / ann["imd"].mean(),
        "monsoon_total_spearman": tot["chirps"].corr(tot["imd"], method="spearman"),
        "monsoon_total_ratio_chirps/imd": tot["chirps"].mean() / tot["imd"].mean(),
        "heavy_days_chirps_also_heavy_in_imd_%": 100 * (hc & hi_near).sum() / max(hc.sum(), 1),
        "years": ann.shape[0],
    }


if __name__ == "__main__":
    a, b = sys.argv[1], sys.argv[2]
    c = load(OUT / f"chirps_district_daily_{a}_{b}.csv", "chirps")
    i = load(OUT / f"imd_district_daily_{a}_{b}.csv", "imd")
    lag = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    i["date"] = i["date"] + pd.Timedelta(days=lag)   # relabel IMD days so they match CHIRPS days
    print(f"lag = {lag} (CHIRPS day d paired with IMD day d{-lag:+d})")
    m = c.merge(i, on=["date", "district"], how="inner")
    print(f"merged rows: {len(m)}  (chirps {len(c)}, imd {len(i)})")
    res = pd.DataFrame({d: agreement(g) for d, g in m.groupby("district")}).T.round(2)
    pd.set_option("display.width", 250)
    print(res.to_string())
    print("\nmedian across districts:\n", res.median().round(2).to_string())
    res.to_csv(OUT / "product_agreement.csv")