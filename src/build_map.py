"""Build docs/index.html: a single self-contained page with the results inlined.

Inputs : docs/data/kerala_districts.geojson   (python src/export_boundaries.py ...)
         docs/data/reliability.json           (python src/reliability.py 1981 2025)
Output : docs/index.html   -> publish with GitHub Pages (Settings > Pages > main /docs)

Usage: python src/build_map.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

geo = json.loads((DOCS / "data" / "kerala_districts.geojson").read_text(encoding="utf-8"))
rel = json.loads((DOCS / "data" / "reliability.json").read_text(encoding="utf-8"))

names = {f["properties"]["name"] for f in geo["features"]}
missing = names - set(rel)
extra = set(rel) - names
if missing or extra:
    raise SystemExit(f"District names do not match. In map but not in results: {sorted(missing)}; "
                     f"in results but not in map: {sorted(extra)}")

# Earth Engine can return a district as a GeometryCollection (e.g. after simplify). Flatten every
# geometry to Polygon/MultiPolygon, keeping only the polygon parts, and say what was found.
def polygons_of(g):
    t = g.get("type")
    if t == "Polygon":
        return [g["coordinates"]]
    if t == "MultiPolygon":
        return list(g["coordinates"])
    if t == "GeometryCollection":
        out = []
        for part in g.get("geometries", []):
            out += polygons_of(part)
        return out
    return []          # points / lines carry no area; ignore

def rnd(c):
    return [round(c[0], 4), round(c[1], 4)] if isinstance(c[0], (int, float)) else [rnd(x) for x in c]

types = {}
for f in geo["features"]:
    g = f.get("geometry") or {}
    types[f["properties"]["name"]] = g.get("type")
    polys = polygons_of(g)
    if not polys:
        raise SystemExit(f"No polygon found for {f['properties']['name']} (geometry type {g.get('type')}). "
                         "Re-run export_boundaries.py, or send me this message.")
    f["geometry"] = {"type": "MultiPolygon", "coordinates": rnd(polys)}
odd = {n: t for n, t in types.items() if t not in ("Polygon", "MultiPolygon")}
print("geometry types:", sorted(set(types.values())), ("-> flattened: " + str(odd)) if odd else "")

html = (ROOT / "src" / "map_template.html").read_text(encoding="utf-8")
data_js = "const DATA = " + json.dumps({"geo": geo, "rel": rel}, separators=(",", ":")) + ";"
assert "/*DATA*/" in html
(DOCS / "index.html").write_text(html.replace("/*DATA*/", data_js), encoding="utf-8")
print(f"Wrote {DOCS / 'index.html'} ({(DOCS / 'index.html').stat().st_size/1e3:.0f} kB), {len(names)} districts")
