"""Validate rainfall products against the official 2018 district totals.

Official = NIDM "Kerala Floods 2018" report, Table 3.1 (source: CWC Hydrological
Studies Organisation, Sept 2018): district rainfall 1 Jun - 22 Aug 2018.

Compares IMD gridded rainfall (downloaded via imdlib) and the CHIRPS district CSV
you already made. Prints actual / official ratios per district.

Usage:
    pip install imdlib
    python src/validate_2018.py
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CHIRPS_CSV = ROOT / "data" / "processed" / "chirps_district_daily_2018_2018.csv"
IMD_DIR = ROOT / "data" / "raw" / "imd"
START, END = "2018-06-01", "2018-08-22"

# NIDM Table 3.1, actual rainfall (mm), 1 Jun - 22 Aug 2018
OFFICIAL = {
    "Alappuzha": 1784.0, "Ernakulam": 2477.8, "Idukki": 3555.5,
    "Kannur": 2573.3, "Kasaragod": 2287.1, "Kollam": 1579.3,
    "Kottayam": 2307.0, "Kozhikode": 2898.0, "Malappuram": 2637.2,
    "Palakkad": 2285.6, "Pathanamthitta": 1968.0,
    "Thiruvananthapuram": 966.7, "Thrissur": 2077.6, "Wayanad": 2884.5,
}


def norm(name: str) -> str:
    """Lowercase, drop ' (State)' suffix and non-letters; unify known spellings."""
    s = str(name).split("(")[0].lower()
    s = "".join(ch for ch in s if ch.isalpha())
    if s.startswith("pat") and "nam" in s:        # Pattanamtitta / Pathanamthitta / Pathanamtitta
        return "pathanamthitta"
    if s in ("kasargod", "kasaragode"):
        return "kasaragod"
    if s == "ernakulum":
        return "ernakulam"
    return s


def window_totals(daily: pd.DataFrame) -> pd.Series:
    """daily: index = dates, one column per district -> total mm over START..END."""
    daily = daily.copy()
    daily.index = pd.to_datetime(daily.index)
    tot = daily.loc[START:END].sum()
    tot.index = [norm(c) for c in tot.index]
    return tot


def r(x):
    """Round, but keep NaN (a NaN means the district name did not match)."""
    return x if pd.isna(x) else round(x)


def compare(chirps: pd.Series, imd: pd.Series | None) -> pd.DataFrame:
    nan = float("nan")
    rows = []
    for name, off in OFFICIAL.items():
        k = norm(name)
        row = {"district": name, "official": round(off)}
        row["chirps"] = r(chirps.get(k, nan))
        row["chirps/off %"] = r(100 * chirps.get(k, nan) / off)
        if imd is not None:
            row["imd"] = r(imd.get(k, nan))
            row["imd/off %"] = r(100 * imd.get(k, nan) / off)
        rows.append(row)
    return pd.DataFrame(rows).sort_values("official", ascending=False)


def load_chirps() -> pd.Series:
    d = pd.read_csv(CHIRPS_CSV)
    wide = d.pivot(index="date", columns="district", values="precip_mm")
    return window_totals(wide)


def load_imd() -> pd.Series:
    import imdlib as imd
    IMD_DIR.mkdir(parents=True, exist_ok=True)
    data = imd.get_data("rain", 2018, 2018, fn_format="yearwise", file_dir=str(IMD_DIR))
    df = data.region(state="Kerala", by="district")   # area-weighted mean per district
    print("IMD columns:", list(df.columns))
    return window_totals(df)


if __name__ == "__main__":
    table = compare(load_chirps(), load_imd())
    pd.set_option("display.width", 200)
    print(table.to_string(index=False))
    print("\nSpearman rank corr with official:")
    off = table["official"]
    for c in [c for c in ("chirps", "imd") if c in table]:
        print(f"  {c}: {table[c].corr(off, method='spearman'):.2f}")
