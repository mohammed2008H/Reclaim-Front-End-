# What the backend does — plain description for the frontend

Two notebooks produce everything the frontend needs. Nothing is computed live in the
browser: the frontend reads the files the notebooks saved into `results/`.

```
notebook 02 (explore)  ->  results/explorer/      pictures + explorer_status.json
notebook 04 (screen)   ->  results/               the screening result (the headline)
                           results/hyperspectral/ optional EnMAP evidence or a "not available" note
```

---

## 1. The study area

* One fixed rectangle over Zankalon, Sharqiya, Egypt: `[31.41, 30.56, 31.46, 30.60]`
  (west, south, east, north; about 4.7 × 4.4 km). It is a pilot rectangle, **not** a farm or
  irrigation boundary.
* It is cut into **1,780 squares of 100 m × 100 m** ("cells"), each with an ID like `R12_C07`
  (row, column). Each cell is nominally 25 Sentinel-2 pixels of 20 m.

## 2. Data that goes in (all public)

| Source | What it gives | Used for |
|---|---|---|
| Sentinel-2 L2A (Element 84 Earth Search STAC) | surface reflectance, 10–20 m, every ~5 days | **the screening result** (notebook 04) and the Feb/Jul pictures (notebook 02) |
| ESA WorldCover 2021, class 40 | which pixels were cropland in 2021 | tells us whether a cell is mostly cropland |
| Planet Tanager open sample (STAC, CC BY 4.0) | 426-band hyperspectral scenes, but **none over Zankalon** | method demonstration only, on a scene in Konya, Türkiye |
| EnMAP (DLR, free account) | hyperspectral over Zankalon, if the user collected a clip | optional extra evidence; status is "not available" unless a real clip is supplied |

The screening itself does not download imagery while it runs. It reads a prepared table
(`data/sample_input/zankalon_grid_monthly_pilot.csv`, 42,720 rows = 1,780 cells × 24 months,
2023 and 2024) that already holds, per cell and month, the median of four indices and their
quality numbers. SHA-256 hashes of the inputs are checked before anything runs.

## 3. The four indices (what the colours mean)

All computed from Sentinel-2 bands; values roughly −1 … +1.

* **NDVI** – green vegetation cover (main signal used for the flags).
* **NDRE** – chlorophyll / canopy vigour (red edge).
* **NDMI** – canopy moisture.
* **BSI** – bare / exposed soil (higher = more bare soil).

## 4. Quality rules (why some cells say "not enough data")

A monthly measurement of a cell is **kept** only if all of these hold:

* processing status is `complete`;
* every index is a finite number;
* ≥ 80 % of the cell's pixels were valid for every index (`MIN_VALID_FRACTION = 0.80`);
* at least 2 clear observations went into the monthly median (`MIN_OBSERVATIONS = 2`).

Missing values are never filled in or interpolated. A cell also needs ≥ 13 of its 25 pixels
to be WorldCover cropland (`MIN_REFERENCE_PIXELS = 13`) to be judged at all.

## 5. The comparison (the actual "algorithm")

1. For each cell, pair the same calendar month in 2023 and 2024 (Jan–Jan, Feb–Feb, …).
2. A pair counts only if **both** months passed the quality rules.
3. Difference = index(2024) − index(2023) for each accepted pair.
4. Per cell: **median NDVI difference** across accepted pairs, plus the same for NDRE, NDMI,
   BSI, and how many months had lower NDVI.
5. A cell is **eligible** if it has ≥ 9 accepted month pairs (`MIN_MATCHED_MONTHS = 9`) and
   enough reference cropland.
6. Status (threshold `CHANGE_THRESHOLD = 0.05` NDVI units):

| status | rule | meaning for the user |
|---|---|---|
| `Review lower greenness` | median NDVI change ≤ −0.05 | **visit first** – greenness clearly lower in 2024 |
| `Smaller net change` | between −0.05 and +0.05 | no strong change |
| `Higher greenness` | median NDVI change ≥ +0.05 | greener in 2024 |
| `Insufficient comparison` | fewer than 9 accepted month pairs | not enough clean data |
| `Limited reference cropland` | < 13 cropland pixels | mostly not cropland in 2021 (village, canal, road) |

Headline numbers: 1,780 cells → 1,519 eligible → **98 "Review lower greenness"**,
1,307 smaller net change, 114 higher greenness, 261 limited reference cropland.

No model is trained, no thresholds were validated against ground truth, and the flags are
**places to investigate, not confirmed degraded farms**. A sensitivity table shows how the
count of flags changes at thresholds 0.03 / 0.05 / 0.08.

## 6. Files the frontend should read (all in `results/`)

| file | what is inside | screen |
|---|---|---|
| `screening_cells.geojson` | one polygon per cell (EPSG from `coordinate_epsg`, UTM 36N; reproject to WGS84 for a web map) with properties: `cell_id`, `status`, `eligible`, `matched_months`, `reference_crop_pixels`, `median_delta_NDVI/NDRE/NDMI/BSI`, `months_with_lower_NDVI`, `reason`, `centre_easting_m`, `centre_northing_m`, `grid_row`, `grid_col` | **map** – colour by `status`; click → details |
| `review_shortlist.csv` | the 98 flagged cells, most negative NDVI change first, with the `reason` sentence | **shortlist / "visit first" list** |
| `cell_comparison_summary.csv` | same columns as the geojson properties, for all 1,780 cells | table / search by cell ID |
| `matched_month_comparisons.csv` | per cell × calendar month: `pair_ok`, each index for 2023 and 2024, `delta_*` | **monthly chart** for a selected cell (2023 line vs 2024 line, 4 small charts; gaps where `pair_ok` is false) |
| `monthly_coverage.csv` | per month: total cells, cells with NDVI, cells passing the quality rule, `retained_fraction` | **data-quality / coverage bar** |
| `threshold_sensitivity.csv` | flags at thresholds 0.03 / 0.05 / 0.08 | small "how robust is this" widget |
| `method_and_provenance.json` | all thresholds, input hashes, source metadata, `counts` per status, `thresholds_validated:false`, `model_trained:false` | **About / method** panel and headline counters |
| `screening_map.png`, `example_comparison.png` | static figures | fallback images / slides |
| `START_HERE.html` | the notebook's own offline dashboard; its embedded JSON (`cells`, `series[cell_id] = {month, accepted, NDVI2023, NDVI2024, …}`, `coverage`, `sensitivity`) is exactly the shape a frontend needs | reference implementation |
| `hyperspectral/` | EnMAP status (`not_available` / `analysis_complete`) and, if complete, a dated red-edge figure per cell | **hyperspectral evidence** panel – show the status text verbatim when not available |
| `explorer/explorer_status.json` | notebook 02 record: Sentinel-2 scenes found (59 in 2024), the two displayed scenes with clear fraction and median NDVI, Tanager coverage (`zankalon_covered_by_open_sample: false`), the Tanager demo stats with `is_zankalon: false` and `pearson_r_meaning`, and any `search_error` | **data sources** page; "method demonstration" badge on the Tanager figure |
| `explorer/sentinel2_2024-02.png`, `sentinel2_2024-07.png`, `hyperspectral_demo.png` | pictures | data sources page |

## 7. Suggested screens (one line each)

1. **Overview** – counters from `method_and_provenance.json.counts`; map coloured by status; legend with the 5 statuses.
2. **Cell detail** (click a cell) – status, `reason` sentence, median change of the 4 indices, 4 monthly charts 2023 vs 2024 from `matched_month_comparisons.csv`, number of accepted months.
3. **Shortlist** – `review_shortlist.csv` as a sortable table; clicking a row flies to the cell.
4. **Data quality** – `monthly_coverage.csv` as bars per month; sensitivity table.
5. **Data sources & hyperspectral** – the two Sentinel-2 pictures, the Tanager figure with a red "method demonstration – not Zankalon" banner, EnMAP status text, and the attribution lines.
6. **Limitations** (always visible, verbatim from the dashboard): cells are not farm boundaries; no ownership data; flags are for investigation, not confirmed degradation; no accuracy percentage was measured; no yield-loss or cost estimate; two years do not establish a long-term trend; crop mask is a static 2021 reference.

## 8. Failure / empty states the frontend must handle

* `status = Insufficient comparison` or `Limited reference cropland` → show "not enough evidence", never a number as if it were a result.
* `pair_ok = false` for a month → gap in the chart, not zero.
* EnMAP `state != analysis_complete` → "Hyperspectral data not analysed" text; no chart.
* `explorer_status.json` has `search_error` → show "catalogue search failed when the notebook ran" instead of scene counts.
* Tanager figure → always carry the "method demonstration, not Zankalon" label; the `r` value is agreement between two indicators on one scene, **not an accuracy score**.
