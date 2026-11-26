# Kerala rainfall extremes by district

**Question:** Which Kerala districts show a statistically supported increase in
extreme daily/multi-day rainfall since 1981, and how do the documented major
flood and landslide events line up with those extremes?

**Not claimed:** flood prediction, or any measure of damage per district.
Damage data at district level is not available in usable form (see Data audit).

## Data audit (fill in as you go)
| Source | What it gives | Years | Format | Problems found |
|---|---|---|---|---|
| CHIRPS v2 (via NOAA ERDDAP) | daily gridded rainfall, 0.05 deg | 1981-present | NetCDF | TODO |
| District boundaries (DataMeet) | 14 district polygons | n/a | GeoJSON | TODO: check district count, Ernakulam boundary |
| EM-DAT (public.emdat.be) | event catalogue, country level | 2000-2026 | xlsx | Admin units stop at state level; district names only in free text |

## Baseline
A district's own historical median of annual max daily rainfall. Any
trend claim must beat "no trend" under a proper test.

## Reproduce
```
pip install -r requirements.txt
python src/fetch_chirps.py 1981 2025
```
Raw data is gitignored and never edited by hand. All cleaning is in `src/`.

## Status
- [ ] Fetch CHIRPS 1981-2025
- [ ] Clip to district polygons
- [ ] Annual max daily rainfall per district + plot
- [ ] Sanity check: 2018 should be extreme in central districts
