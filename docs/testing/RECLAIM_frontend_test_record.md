# RECLAIM frontend test record
Date: 2026-10-11 · Tester: Devin (automated, tests/criteria_check_zankalon.py) · App: Reclaim production build (vite build) · Data: results of notebook 04 v1.0 + explorer notebook 02
Device/browser: Chrome 137 (Devin VM, Linux) · WebGL: ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero) (0x0000C0DE)), SwiftShader driver)

Note: software WebGL on this VM (no GPU): the globe renders at ~1-3 fps here, so camera flights are slow; a laptop GPU is far faster

| ID | Check | Status | Actual result / note | Evidence |
|---|---|---|---|---|
| T17 | dashboard usable within 5 s (5 openings; max 9.03 s) | **FAIL** | 8.88 8.68 9.03 8.60 8.84 | criteria_results.json |
| T12 | selector lists 1,780 unique cells = summary CSV ids | **PASS** | 1780 | T12_selector_cell_detail.png, T12_map_click.png |
| T12 | 20 selector picks: id, category, explanation, months, crop pixels, centre (UTM to the metre, lat/lon within 1 m) | **PASS** | [] | T12_selector_cell_detail.png, T12_map_click.png |
| T17 | 20 cell selections: details + 4 charts updated within 1 s (max 14 ms, measured in-page; the camera flight is a separate animation) | **PASS** | — | criteria_results.json |
| T12 | 20 map clicks: clicked square = hovered id = panel id with correct category | **PASS** | [] | T12_selector_cell_detail.png, T12_map_click.png |
| T12 | cell ring ≈ 100 m (101.4 × 101.1 m), camera north-up after fly | **PASS** | heading=0.0 | T12_selector_cell_detail.png, T12_map_click.png |
| T13 | 10 cells: every plotted point = source value (3 dp), rejected months drawn as gaps not zero, panel medians = summary (3 dp) = independent median from the 4-dp pair table | **PASS** | [] | T13_charts_with_excluded_months.png |
| T19 | EnMAP shown as not available (no completed hyperspectral input); Sentinel-only result stated | **PASS** | — | T20_sources_run_record.png |
| T19 | Tanager scene labelled method demonstration, outside Zankalon (scene id + date shown), not an accuracy score | **PASS** | — | T20_sources_run_record.png |
| T20 | sources, dates, settings and all 4 input SHA-256 checksums visible | **PASS** | — | T20_sources_run_record.png, T20_limitations.png |
| T20 | flags need field investigation; no accuracy/yield/confirmed-degradation claims | **PASS** | — | T20_sources_run_record.png, T20_limitations.png |
| T14 | legend counts = provenance counts; shortlist 98 rows in CSV order | **PASS** | — | T14_offline.png |
| T14 | shortlist CSV download served and identical to notebook file | **PASS** | — | T14_offline.png |
| T14 | offline (all external hosts blocked): app loads, cell selection, charts and method details work; base map tiles absent | **PASS** | [] | T14_offline.png |
| T14 | static files with JavaScript disabled | **N/A** | the globe app needs JavaScript; the notebook results package (START_HERE.html + CSV/GeoJSON/PNG) covers this | T14_offline.png |
| T15 | 1366 px Chrome: no horizontal scroll, header/toolbar/mode switch do not overlap, controls on screen, text ≥ 10 px | **PASS** | {'tb_brand': False, 'tb_mode': False, 'brand_mode': False, 'tb_readout': False, 'readout_leftcol': False, 'leftcol_rightcol': False, 'rightcol_dock': False} small=0 ctrls=True | T15_1366px.png, T15_390px.png, T15_keyboard_focus.png |
| T15 | keyboard: select a cell via selector and shortlist row, open method details; focus visible | **PASS** | True True True vis=True True | T15_1366px.png, T15_390px.png, T15_keyboard_focus.png |
| T15 | categories named in text (legend, cell panel, hover tip), not colour only | **PASS** | — | T15_1366px.png, T15_390px.png, T15_keyboard_focus.png |
| T15 | 390 px Chrome: no horizontal scroll, header/toolbar/mode switch do not overlap, controls on screen, text ≥ 10 px | **PASS** | {'tb_brand': False, 'tb_mode': False, 'brand_mode': False, 'tb_readout': False, 'readout_leftcol': False, 'leftcol_rightcol': False, 'rightcol_dock': False} small=0 ctrls=True | T15_1366px.png, T15_390px.png, T15_keyboard_focus.png |
| T15 | Edge browser | **BLOCKED** | Edge is not installed on this Linux test machine (Chrome only) | T15_1366px.png, T15_390px.png, T15_keyboard_focus.png |
| — | no page errors in any run | **PASS** | [] |  |
| T17 | dashboard opening, single tab after idle (3 openings; max 9.45 s) | **FAIL** | 9.45 9.44 9.02 | criteria_results.json |
| T17 | dashboard opening after resetting the browser GPU process (3 openings, single tab; max 5.20 s) | **FAIL** | 1.74 1.36 5.20 s. The ~9 s figures above were measured while the VM's software-rendering GPU process was saturated by the preceding test pages; the app itself (65 kB JS + 2.5 MB data) is not the bottleneck. Please time it once on a normal laptop. | criteria_results.json |

## Criteria not covered by the frontend run

| ID | Status | Note |
|---|---|---|
| T01 | PASS (earlier backend verification) | Verified 2026-10-05 when notebook 04 was run here: all 6 input hashes matched, 1,780 cells, 42,720 monthly rows. |
| T02 | NOT TESTED HERE (backend) | Notebook 02/03 behaviour (scene selection < 20 % tile cloud, SCL 4/5 mask). Not a frontend test; collection notebook 03 was not re-run here. |
| T03 | NOT TESTED HERE (backend) | Backend index arithmetic; not a frontend test. |
| T04 | NOT TESTED HERE (backend) | Backend quality rule; the frontend only displays the pass/fail flags from matched_month_comparisons.csv. |
| T05 | NOT TESTED HERE (backend) | Backend pairing; frontend charts were checked against the exported pairs (T13). |
| T06 | PASS (earlier backend verification) | Re-derived independently on 2026-10-05: every cell's median NDVI change and status matched the notebook output. |
| T07 | NOT TESTED HERE (backend) | Backend rule; counts shown in the frontend equal the notebook counts (T14). |
| T08 | NOT TESTED HERE (backend) | Backend rule. |
| T09 | PASS (earlier backend verification) | Notebook 04 run three ways (your Colab run, local nbconvert, local clone layout) gave byte-identical tables. |
| T10 | PASS (earlier backend verification) | Frontend shortlist checked: same 98 cells, same order as review_shortlist.csv, download identical (T14). |
| T11 | PASS (earlier backend verification) | Threshold sensitivity table (0.03 / 0.05 / 0.08) is shown in the Data quality panel from threshold_sensitivity.csv; 0.05 row = 98. |
| T16 | BLOCKED | Needs five first-time users; cannot be done by automation. The four usability tasks are all possible in the UI (find a Review cell, read its NDVI change and matched months, see a lower-NDVI month on the charts, read the "flag ≠ confirmed degradation" note). |
| T18 | NOT TESTED HERE (backend) | Notebook 02/04 error handling (hash mismatch, failed catalogue search reported as search_error). The frontend refuses to draw if cells/meta/series disagree. |