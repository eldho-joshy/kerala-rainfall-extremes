"""Per-district reliability tiers from three-product agreement.

For each district and each measure (annual max 7-day rainfall = "extremes"; Jun-Sep total = "totals"):
  * Spearman correlation of the 45 yearly values for each pair of products
  * 95% bootstrap CI per pair (resample years)
  * Tier, fixed in advance:
      "agree"   : all three pairs have CI lower bound > 0
      "partial" : at least one pair has CI lower bound > 0, but not all three
      "none"    : no pair has CI lower bound > 0  (no demonstrated agreement)

Tiers describe CONSISTENCY between products, not accuracy. 14 districts x 3 pairs are tested
with no multiple-comparison correction, and 45 years gives wide intervals.

Usage: python src/reliability.py 1981 2025 [n_boot]
Writes data/processed/reliability_tiers.csv and docs/data/reliability.json
"""
import itertools
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import three_way as tw   # same folder; reuses loading, alignment and Spearman helpers

OUT = tw.OUT
DOCS = Path(__file__).resolve().parents[1] / "docs" / "data"
MEASURES = {"extremes": ("7", "annual max 7-day rainfall"),
            "totals": ("monsoon", "Jun-Sep rainfall total")}


def tier_of(lows: dict) -> str:
    n = sum(v > 0 for v in lows.values())
    return "agree" if n == 3 else ("partial" if n >= 1 else "none")


def main(a: str, b: str, n_boot: int):
    rng = np.random.default_rng(42)
    w = {k: tw.wide(OUT / f.format(a=a, b=b)) for k, f in tw.FILES.items()}
    for k in ("imd", "era5"):
        lag = tw.best_lag(w["chirps"], w[k])
        print(f"{k}: lag {lag}")
        w[k] = w[k].shift(lag)
    cols = list(w["chirps"].columns)
    pairs = [f"{p}-{q}" for p, q in itertools.combinations(w, 2)]

    rows, js = [], {c: {} for c in cols}
    for key, (stat, label) in MEASURES.items():
        ann = {k: tw.annual_stat(w[k], stat) for k in w}
        arr = {k: ann[k].loc[ann["chirps"].index, cols].to_numpy() for k in w}
        ok = np.ones(arr["chirps"].shape[0], dtype=bool)
        for k in arr:
            ok &= ~np.isnan(arr[k]).any(1)
        arr = {k: v[ok] for k, v in arr.items()}
        n = arr["chirps"].shape[0]
        point = {p: tw.spearman_cols(arr[p.split("-")[0]], arr[p.split("-")[1]]) for p in pairs}
        bs = {p: np.empty((n_boot, len(cols))) for p in pairs}
        for i in range(n_boot):
            idx = rng.integers(0, n, n)
            for p in pairs:
                x, y = p.split("-")
                bs[p][i] = tw.spearman_cols(arr[x][idx], arr[y][idx])
        for j, c in enumerate(cols):
            lo = {p: float(np.percentile(bs[p][:, j], 2.5)) for p in pairs}
            hi = {p: float(np.percentile(bs[p][:, j], 97.5)) for p in pairs}
            r = {p: float(point[p][j]) for p in pairs}
            t = tier_of(lo)
            rows.append({"district": c, "measure": key, "tier": t, "mean_r": np.mean(list(r.values())),
                         **{f"{p}_r": r[p] for p in pairs}, **{f"{p}_lo": lo[p] for p in pairs},
                         **{f"{p}_hi": hi[p] for p in pairs}, "years": n})
            js[c][key] = {"label": label, "tier": t, "years": n, "mean_r": round(float(np.mean(list(r.values()))), 2),
                          "pairs": {p: {"r": round(r[p], 2), "lo": round(lo[p], 2), "hi": round(hi[p], 2)} for p in pairs}}
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "reliability_tiers.csv", index=False)
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "reliability.json").write_text(json.dumps(js, indent=1))
    pd.set_option("display.width", 200)
    for key in MEASURES:
        print(f"\n== {key} ==")
        print(df[df.measure == key][["district", "tier", "mean_r"]].round(2).sort_values("mean_r", ascending=False).to_string(index=False))
        print(df[df.measure == key].tier.value_counts().to_string())


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 2000)
