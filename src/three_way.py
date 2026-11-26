"""Three-way agreement between CHIRPS, IMD and ERA5-Land, with bootstrap CIs.

1. Finds the day alignment of IMD and ERA5-Land relative to CHIRPS (best lag in -2..2).
2. For several time scales, takes each product's annual maximum k-day total (and monsoon /
   annual totals) per district and rank-correlates the yearly values for each PAIR of products.
3. Bootstraps over years (resample the 45 years with replacement) to get a 95% CI for the
   median agreement across districts, and for Idukki and Wayanad separately.
4. Reports which pair agrees most; the remaining product is a candidate outlier,
   but only "clear" when the CIs separate. Agreement = consistency, NOT accuracy.

Usage: python src/three_way.py 1981 2025 [n_boot]
Writes data/processed/three_way_agreement.csv (per district) and three_way_summary.csv
"""
import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata

OUT = Path(__file__).resolve().parents[1] / "data" / "processed"
RENAME = {"Pattanamtitta": "Pathanamthitta"}
FILES = {"chirps": "chirps_district_daily_{a}_{b}.csv",
         "imd": "imd_district_daily_{a}_{b}.csv",
         "era5": "era5land_district_daily_{a}_{b}.csv"}
WINDOWS = [1, 3, 7, 15, 30]
FOCUS = ["Idukki", "Wayanad"]


def wide(path: Path) -> pd.DataFrame:
    d = pd.read_csv(path, parse_dates=["date"])
    d["district"] = d["district"].replace(RENAME)
    return d.pivot(index="date", columns="district", values="precip_mm").sort_index()


def best_lag(ref: pd.DataFrame, other: pd.DataFrame, lags=range(-2, 3)) -> int:
    """k maximising monsoon daily Pearson when ref day d is paired with other day d-k."""
    jjas = ref.index.month.isin([6, 7, 8, 9])
    score = {k: ref[jjas].corrwith(other.shift(k)[jjas]).median() for k in lags}
    print("   lag scores:", {k: round(v, 3) for k, v in score.items()})
    return max(score, key=score.get)


def annual_stat(w: pd.DataFrame, name: str) -> pd.DataFrame:
    if name == "monsoon":
        m = w[w.index.month.isin([6, 7, 8, 9])]
        return m.groupby(m.index.year).sum()
    if name == "annual":
        return w.groupby(w.index.year).sum()
    k = int(name)
    roll = w.rolling(k, min_periods=k).sum()
    return roll.groupby(roll.index.year).max()


def spearman_cols(A: np.ndarray, B: np.ndarray) -> np.ndarray:
    ra, rb = rankdata(A, axis=0), rankdata(B, axis=0)
    ra, rb = ra - ra.mean(0), rb - rb.mean(0)
    return (ra * rb).sum(0) / np.sqrt((ra ** 2).sum(0) * (rb ** 2).sum(0))


def boot_paired(arrs: dict, pairs: list, cols: list, n_boot: int, rng):
    """Resample years ONCE per replicate and compute every pair on that same resample,
    so differences between pairs can be tested properly."""
    n = next(iter(arrs.values())).shape[0]
    med = {p: [] for p in pairs}
    foc = {(p, c): [] for p in pairs for c in FOCUS}
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        for p in pairs:
            a, b = p.split("-")
            r = spearman_cols(arrs[a][idx], arrs[b][idx])
            med[p].append(np.nanmedian(r))
            for c in FOCUS:
                foc[(p, c)].append(r[cols.index(c)])
    return {p: np.array(v) for p, v in med.items()}, {k: np.array(v) for k, v in foc.items()}


def main(a: str, b: str, n_boot: int):
    rng = np.random.default_rng(42)
    w = {k: wide(OUT / f.format(a=a, b=b)) for k, f in FILES.items()}
    print("Aligning to CHIRPS days:")
    for k in ("imd", "era5"):
        lag = best_lag(w["chirps"], w[k])
        print(f" {k}: best lag {lag} (CHIRPS day d paired with {k} day d{-lag:+d})")
        w[k] = w[k].shift(lag)

    cols = list(w["chirps"].columns)
    stats = [str(k) for k in WINDOWS] + ["monsoon", "annual"]
    rows, per_district, verdicts = [], [], []
    pairs = [f"{p}-{q}" for p, q in itertools.combinations(w, 2)]
    for s_ in stats:
        ann = {k: annual_stat(w[k], s_) for k in w}
        yrs = ann["chirps"].index
        arr = {k: ann[k].loc[yrs, cols].to_numpy() for k in w}
        ok = np.ones(len(yrs), dtype=bool)
        for k in arr:
            ok &= ~np.isnan(arr[k]).any(1)
        arr = {k: v[ok] for k, v in arr.items()}
        med, foc = boot_paired(arr, pairs, cols, n_boot, rng)
        point = {}
        for pr in pairs:
            x, y = pr.split("-")
            r = spearman_cols(arr[x], arr[y])
            point[pr] = np.median(r)
            lo, hi = np.percentile(med[pr], [2.5, 97.5])
            row = {"stat": s_, "pair": pr, "median_r": point[pr], "median_lo": lo, "median_hi": hi,
                   "years": int(ok.sum())}
            for c in FOCUS:
                l2, h2 = np.percentile(foc[(pr, c)], [2.5, 97.5])
                row.update({f"{c}_r": r[cols.index(c)], f"{c}_lo": l2, f"{c}_hi": h2})
            rows.append(row)
            per_district += [{"stat": s_, "pair": pr, "district": c, "spearman": v}
                             for c, v in zip(cols, r)]
        order = sorted(pairs, key=lambda q: point[q], reverse=True)
        best, second = order[0], order[1]
        diff = med[best] - med[second]          # same resamples -> valid paired difference
        dlo, dhi = np.percentile(diff, [2.5, 97.5])
        outlier = (set(w) - set(best.split("-"))).pop()
        verdicts.append((s_, best, point[best], second, point[second], dlo, dhi, outlier,
                         "CLEAR" if dlo > 0 else "unclear"))
    res = pd.DataFrame(rows)
    pd.DataFrame(per_district).to_csv(OUT / "three_way_agreement.csv", index=False)
    res.to_csv(OUT / "three_way_summary.csv", index=False)

    pd.set_option("display.width", 250)
    show = res.copy()
    show["median (95% CI)"] = show.apply(lambda x: f"{x.median_r:.2f} [{x.median_lo:.2f}, {x.median_hi:.2f}]", axis=1)
    show["Idukki"] = show.apply(lambda x: f"{x.Idukki_r:.2f} [{x.Idukki_lo:.2f}, {x.Idukki_hi:.2f}]", axis=1)
    show["Wayanad"] = show.apply(lambda x: f"{x.Wayanad_r:.2f} [{x.Wayanad_lo:.2f}, {x.Wayanad_hi:.2f}]", axis=1)
    print("\n", show[["stat", "pair", "median (95% CI)", "Idukki", "Wayanad"]].to_string(index=False))

    print("\nBest pair vs second-best, tested on the SAME resamples (paired bootstrap):")
    print("  diff = (best pair median) - (second pair median); CLEAR only if the 95% CI of diff is above 0")
    for (s_, best, rb, second, rs, dlo, dhi, outlier, tag) in verdicts:
        print(f"  {s_:>8}: {best} {rb:.2f} vs {second} {rs:.2f}; diff CI [{dlo:+.2f}, {dhi:+.2f}] "
              f"-> {tag}; candidate outlier: {outlier}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 1000)
