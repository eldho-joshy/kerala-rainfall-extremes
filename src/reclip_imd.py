"""Re-clip IMD 0.25 deg rainfall to the SAME district polygons (FAO GAUL 2015) used for CHIRPS and ERA5-Land.

Why: export_imd.py uses imdlib's built-in district outlines; the other two products use GAUL.
If outlines differ, part of the "disagreement" could be geometry, not rain. This removes that confound.

Each 0.25 deg cell is split into SUB x SUB sub-points; a district's weight for a cell is the
fraction of sub-points inside the polygon (area weighting). Days with NaN cells are re-normalised.

Needs the raw files already downloaded by export_imd.py (data/raw/imd/rain/<year>.grd).
Output: data/processed/imd_gaul_district_daily_<start>_<end>.csv  (date, district, precip_mm)

Usage: python src/reclip_imd.py 1981 2025
"""
import json
import sys
from pathlib import Path

import imdlib as imd
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
IMD_DIR = ROOT / "data" / "raw" / "imd"
OUT = ROOT / "data" / "processed"
GEOJSON = ROOT / "docs" / "data" / "kerala_districts.geojson"
SUB = 10
STEP = 0.25


def rings_of(geom):
    """List of polygons; each = [outer, hole1, ...]. Flattens GeometryCollections (as build_map.py does);
    ignores any non-polygon parts (points/lines)."""
    t = geom["type"]
    if t == "Polygon":
        return [geom["coordinates"]]
    if t == "MultiPolygon":
        return list(geom["coordinates"])
    if t == "GeometryCollection":
        return [p for g in geom["geometries"] for p in rings_of(g)]
    return []


def in_ring(px, py, ring):
    """Ray casting, vectorised over points."""
    ring = np.asarray(ring)
    x, y = ring[:, 0], ring[:, 1]
    inside = np.zeros(px.shape, dtype=bool)
    j = len(ring) - 1
    for i in range(len(ring)):
        cond = (y[i] > py) != (y[j] > py)
        with np.errstate(divide="ignore", invalid="ignore"):
            xin = (x[j] - x[i]) * (py - y[i]) / (y[j] - y[i]) + x[i]
        inside ^= cond & (px < xin)
        j = i
    return inside


def in_geom(px, py, geom):
    res = np.zeros(px.shape, dtype=bool)
    for poly in rings_of(geom):
        m = in_ring(px, py, poly[0])
        for hole in poly[1:]:
            m &= ~in_ring(px, py, hole)
        res |= m
    return res


def weights(lats, lons, features):
    """(n_districts, n_lat, n_lon) fraction of each cell inside each district."""
    off = (np.arange(SUB) + 0.5) / SUB * STEP - STEP / 2
    W = np.zeros((len(features), len(lats), len(lons)))
    for a, lat in enumerate(lats):
        for b, lon in enumerate(lons):
            px, py = np.meshgrid(lon + off, lat + off)
            px, py = px.ravel(), py.ravel()
            for k, f in enumerate(features):
                if (px.max() < f["bbox"][0] or px.min() > f["bbox"][2]
                        or py.max() < f["bbox"][1] or py.min() > f["bbox"][3]):
                    continue
                W[k, a, b] = in_geom(px, py, f["geometry"]).mean()
    return W


def load_features():
    g = json.load(open(GEOJSON))
    feats = []
    for f in g["features"]:
        pts = np.array([c for poly in rings_of(f["geometry"]) for c in poly[0]])
        feats.append({"name": f["properties"]["name"], "geometry": f["geometry"],
                      "bbox": (pts[:, 0].min(), pts[:, 1].min(), pts[:, 0].max(), pts[:, 1].max())})
    return feats


def year_table(y, feats, cache):
    data = imd.open_data("rain", y, y, "yearwise", str(IMD_DIR))
    ds = data.get_xarray()
    var = list(ds.data_vars)[0]
    da = ds[var].where(ds[var] > -900)           # IMD missing value is -999
    lats, lons = da["lat"].values, da["lon"].values
    box = (lats >= 7.9) & (lats <= 13.0), (lons >= 74.5) & (lons <= 77.8)
    sub = da.isel(lat=np.where(box[0])[0], lon=np.where(box[1])[0])
    la, lo = sub["lat"].values, sub["lon"].values
    key = (tuple(np.round(la, 3)), tuple(np.round(lo, 3)))
    if key not in cache:
        cache[key] = weights(la, lo, feats)
        print("   weights built:", cache[key].sum(axis=(1, 2)).round(2).tolist())
    W = cache[key]
    X = sub.values                                  # (time, lat, lon)
    ok = ~np.isnan(X)
    Xf = np.where(ok, X, 0.0)
    rows = []
    for k, f in enumerate(feats):
        num = (Xf * W[k]).sum(axis=(1, 2))
        den = (ok * W[k]).sum(axis=(1, 2))
        with np.errstate(divide="ignore", invalid="ignore"):
            rows.append(pd.DataFrame({"date": pd.to_datetime(sub["time"].values).strftime("%Y-%m-%d"),
                                      "district": f["name"],
                                      "precip_mm": np.where(den > 0, num / den, np.nan)}))
    return pd.concat(rows)


if __name__ == "__main__":
    start, end = int(sys.argv[1]), int(sys.argv[2])
    feats = load_features()
    assert len(feats) == 14, len(feats)
    cache, frames = {}, []
    for y in range(start, end + 1):
        t = year_table(y, feats, cache)
        print(f"{y}: {len(t)} rows, NaNs: {t['precip_mm'].isna().sum()}")
        frames.append(t)
    full = pd.concat(frames).sort_values(["district", "date"])
    out = OUT / f"imd_gaul_district_daily_{start}_{end}.csv"
    full.round(3).to_csv(out, index=False)
    print(f"Wrote {out} ({len(full)} rows)")