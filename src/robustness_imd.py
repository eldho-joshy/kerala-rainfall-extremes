"""Does re-clipping IMD with the GAUL polygons change the agreement results?

Compares, per district, the rank agreement (Spearman over 45 years) of
CHIRPS-IMD and IMD-ERA5 using (a) imdlib outlines (original) and (b) GAUL polygons.
Also checks the new IMD series is the same rain, just re-clipped (correlation with the original).
Does not overwrite any existing output.

Usage: python src/robustness_imd.py 1981 2025
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import three_way as tw

OUT = Path(__file__).resolve().parents[1] / "data" / "processed"
RES = Path(__file__).resolve().parents[1] / "results"


def main(a, b):
    chirps = tw.wide(OUT / f"chirps_district_daily_{a}_{b}.csv")
    era5 = tw.wide(OUT / f"era5land_district_daily_{a}_{b}.csv")
    old = tw.wide(OUT / f"imd_district_daily_{a}_{b}.csv")
    new = tw.wide(OUT / f"imd_gaul_district_daily_{a}_{b}.csv")
    cols = list(chirps.columns)
    new = new[cols]
    era5 = era5.shift(tw.best_lag(chirps, era5))
    old = old.shift(tw.best_lag(chirps, old))
    new = new.shift(tw.best_lag(chirps, new))

    jjas = old.index.month.isin([6, 7, 8, 9])
    same = old[jjas].corrwith(new[jjas])
    print("\nDaily monsoon correlation, IMD original vs IMD re-clipped (should be ~0.9+):")
    print(same.round(3).to_string())

    rows = []
    for stat in ("7", "monsoon"):
        A = {k: tw.annual_stat(v, stat).loc[:, cols] for k, v in
             {"chirps": chirps, "era5": era5, "imd_old": old, "imd_new": new}.items()}
        yrs = A["chirps"].index
        arr = {k: v.loc[yrs].to_numpy() for k, v in A.items()}
        ok = np.ones(len(yrs), bool)
        for v in arr.values():
            ok &= ~np.isnan(v).any(1)
        arr = {k: v[ok] for k, v in arr.items()}
        for pair in (("chirps", "imd"), ("era5", "imd")):
            r_old = tw.spearman_cols(arr[pair[0]], arr["imd_old"] if pair[1] == "imd" else None)
            r_new = tw.spearman_cols(arr[pair[0]], arr["imd_new"])
            for i, d in enumerate(cols):
                rows.append({"stat": stat, "pair": f"{pair[0]}-imd", "district": d,
                             "r_original": r_old[i], "r_gaul": r_new[i], "diff": r_new[i] - r_old[i]})
    df = pd.DataFrame(rows)
    print("\nChange in agreement when IMD uses GAUL polygons (r_gaul - r_original):")
    for (stat, pair), g in df.groupby(["stat", "pair"]):
        print(f" {stat:8s} {pair:12s} median r {g.r_original.median():.2f} -> {g.r_gaul.median():.2f}"
              f" | median |diff| {g['diff'].abs().median():.2f}, max |diff| {g['diff'].abs().max():.2f}"
              f" ({g.loc[g['diff'].abs().idxmax(), 'district']})")
    focus = df[(df.stat == "7") & df.district.isin(["Wayanad", "Idukki", "Pathanamthitta"])]
    print("\nGhats districts, 7-day max:")
    print(focus.round(2).to_string(index=False))
    RES.mkdir(exist_ok=True)
    df.round(3).to_csv(RES / "imd_polygon_robustness.csv", index=False)
    print("\nWrote results/imd_polygon_robustness.csv")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
