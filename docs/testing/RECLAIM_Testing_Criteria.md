# RECLAIM Platform Testing Criteria

Zankalon pilot study, Sharqiya, Egypt

# 1 Purpose and scope

These criteria assess whether RECLAIM produces correct, consistent and understandable screening results. The platform compares satellite observations to help agricultural advisers identify locations that require field investigation. This document defines planned acceptance tests and does not report completed testing.

The core assessment covers the Sentinel-2 analysis for 2023 and 2024, the interactive dashboard and exported results. EnMAP analysis is assessed separately when real hyperspectral data are available. Successful software tests do not establish the accuracy of land degradation detection.

# 2 Reference settings

| Item | Reference setting |
|---|---|
| Study area | Zankalon rectangle from 31.41 to 31.46 degrees east and 30.56 to 30.60 degrees north. Analysis cells are approximately 100 m wide. |
| Input package | 1,780 cells and 42,720 monthly records across 24 months. WorldCover 2021 provides the cropland reference. |
| Measurement quality | All four indices must be finite. Each index requires at least 80 percent valid reference crop pixels and a median observation count of at least 2. Processing must be complete. |
| Cell eligibility | At least 13 reference crop pixels out of 25 nominal pixels and at least 9 matched calendar months. |
| Change calculation | Subtract each accepted 2023 monthly value from its 2024 value for the same cell and month. Calculate the median of these monthly differences. |
| Classification | Median NDVI change at or below -0.05 indicates Review lower greenness. At or above 0.05 indicates Higher greenness. Values strictly between these limits indicate Smaller net change. |

# 3 Testing procedure

Use the unchanged reference package for baseline tests and separate copies for invalid inputs and boundary cases. Record the data version, settings, software versions, device and browser. Numerical comparisons use unrounded values unless a display precision is specified. Performance and usability limits below are proposed acceptance targets.

For every criterion, record the actual result, Pass, Fail or Blocked status, test date, tester and an evidence file. A test is Blocked when required data or access are unavailable. All criteria begin as Not tested.

# 4 Data quality and numerical accuracy

These tests check that the platform accepts suitable data and calculates reliable intermediate values. Preserve the original reference package throughout testing.

| ID | Criterion and test method | Measurable pass condition |
|---|---|---|
| T01 | Input integrity Load the reference package. Compare its checksums, cell identifiers and monthly records with the manifest. | All required checksums match. The package contains exactly 1,780 unique cells and 42,720 unique cell and month records. Table and geometry identifiers match with no missing or duplicate identifiers. Retain the validation log. |
| T02 | Image quality screening Inspect the scene selection record and the pixel mask from the Sentinel-2 workflow. | Selected scenes have tile cloud cover below 20 percent. Every retained pixel lies within the study area, has valid required bands and belongs to scene classification class 4 or 5. No cloud, shadow, water or no-data pixel contributes to an index. Save mask counts and the selected scene record. |
| T03 | Index calculation Independently calculate NDVI, NDRE, NDMI and BSI for 20 valid pixels using the documented band choices. Test zero denominators separately. | All 80 calculated values differ from the independent results by no more than 0.000001 index units. NDRE uses B8A and B05. Undefined calculations remain missing and are excluded. Save the reference calculations and differences. |
| T04 | Measurement acceptance Vary one quality input at a time. Test valid fractions of 0.79, 0.80 and 0.81, observation counts of 1, 2 and 3, missing indices and incomplete processing. | With all other requirements met, 0.80 and 2 are accepted. Values below either limit are rejected. A missing or non-finite value in any index, or incomplete processing, rejects the measurement. Every test case follows these rules. |
| T05 | Matching across years Inspect 20 monthly pairs and controlled examples with a missing year, different calendar months or a rejected measurement. | Every retained pair contains the same cell and calendar month in 2023 and 2024. Both measurements pass T04. Unmatched or rejected observations never enter the change calculation and are never replaced by zero. Save the pairing audit. |
| T06 | Change and median calculation Independently recalculate monthly differences and their medians for 20 cells across all four indices. | All 80 median results agree within 0.000001 index units. The calculation uses 2024 minus 2023. A change from 0.70 to 0.60 produces -0.10. Cells with no accepted pairs retain a missing median. Save the comparison worksheet. |

# Index definitions

NDVI is the Normalized Difference Vegetation Index. NDRE is the Normalized Difference Red Edge Index. NDMI is the Normalized Difference Moisture Index. BSI is the Bare Soil Index. These indicators describe spectral conditions and do not directly measure crop yield or establish the cause of a change.

# 5 Classification and reproducibility

These tests verify the screening rules and the consistency of the investigation shortlist. The reference counts apply only to the unchanged pilot data and default settings.

| ID | Criterion and test method | Measurable pass condition |
|---|---|---|
| T07 | Eligibility boundaries Test cells with 12 and 13 reference crop pixels and with 8 and 9 accepted matched months. | A greenness category is assigned only when both limits are met. Fewer than 13 crop pixels gives Limited reference cropland. Otherwise, fewer than 9 months gives Insufficient comparison. When both fail, Limited reference cropland takes precedence. All cases receive the correct label. |
| T08 | Classification boundaries For eligible cells, test median NDVI changes of -0.051, -0.050, -0.049, 0.049, 0.050 and 0.051. | The first two values receive Review lower greenness. The middle two receive Smaller net change. The last two receive Higher greenness. All six labels match. Classification uses full precision rather than rounded display values. |
| T09 | Reproduction of the baseline Run the main analysis three times from clean sessions using the same reference package and settings. | Every run matches all reference counts below. All cell identifiers, eligibility decisions and category assignments are identical. Corresponding numerical summaries agree within 0.000001 index units. Retain the three run logs and comparison report. |
| T10 | Investigation shortlist Compare every exported shortlist record with the full cell summary. | The shortlist contains exactly the 98 Review lower greenness cells, each once. No other category is included. Every record includes its cell identifier, coordinates, change, matched months and explanation. Sort order is increasing NDVI change, then cell identifier for ties. |
| T11 | Threshold sensitivity Repeat classification using NDVI thresholds of 0.03, 0.05 and 0.08 without changing input data or eligibility rules. | All three runs contain 1,519 eligible cells. The number of review flags cannot increase as the threshold rises. The 0.05 run contains 98 flags. Exported sensitivity counts equal independently counted labels for every threshold. |

# Reference output counts

| Output | Expected count |
|---|---|
| All analysis cells | 1,780 |
| Eligible cells | 1,519 |
| Review lower greenness | 98 |
| Smaller net change | 1,307 |
| Higher greenness | 114 |
| Limited reference cropland | 261 |
| Insufficient comparison | 0 |

# 6 Dashboard quality and user experience

Assess the final exported dashboard in Chrome and Edge and record both browser versions. Proposed usability targets apply to this pilot and should be evaluated through the tasks below.

| ID | Criterion and test method | Measurable pass condition |
|---|---|---|
| T12 | Map and cell selection Check all map identifiers. Inspect 20 cells across the available categories through both map clicks and the cell selector. | The map and selector contain all 1,780 cells without duplicates. All 20 selections show the correct identifier, category, explanation, matched-month count and centre coordinates. Coordinates match exported values to the displayed metre. Map orientation and the 100 m cell scale are correct. |
| T13 | Charts and missing observations Compare the four charts for 10 cells with the monthly comparison table. Include a controlled case with excluded months. | Every plotted month and year matches its source record. Displayed values agree after rounding to three decimal places. Rejected months appear as gaps. Missing observations are never drawn as zero. The median change shown in the detail panel matches the summary to three decimal places. |
| T14 | Exports and offline use Open the final results package and compare the dashboard, CSV tables, GeoJSON and figures. Repeat dashboard checks with the network disconnected. | Required files open without errors. Summary CSV and GeoJSON contain 1,780 unique cells and the shortlist contains 98. Labels and counts agree across all outputs. Cell selection, charts and method details work offline. Static files remain available when JavaScript is disabled. |
| T15 | Readability and keyboard use Check the dashboard at viewport widths of 390 and 1366 pixels in both browsers. Navigate the cell selector and expandable sections using the keyboard. | All four browser and width combinations show readable text and complete controls without page-wide horizontal scrolling or overlap. Keyboard users can select a cell and open method details with visible focus. Categories are named in text and do not depend on colour alone. |
| T16 | Usability and interpretation Ask five first-time users to complete the four tasks below without coaching. Record completion, elapsed time and answers. | At least four of five users complete all four tasks correctly in five minutes per user. Those successful users explain that a flag requires investigation and does not confirm degradation. Record individual results rather than reporting an unsupported general satisfaction score. |

# Tasks for the usability test

1. Find a cell labelled Review lower greenness and state its cell identifier.

2. Report its median NDVI change and the number of matched months.

3. Use its charts to identify one accepted month with lower NDVI in 2024.

4. Explain what the flag means and identify one field check before drawing a conclusion.

Select a test cell that has at least one accepted month with lower NDVI. Use participants who resemble the intended users where possible. Record participant background so the limits of this small usability study remain clear.

# 7 Performance and reliable operation

The following timing limits are proposed targets for the pilot. Record the device and runtime configuration so repeated measurements can be compared fairly.

| ID | Criterion and test method | Measurable pass condition |
|---|---|---|
| T17 | Processing and response time Measure three clean analysis runs, five dashboard openings and 20 cell selections on the recorded test device. | Each core analysis run finishes within 120 seconds after dependencies and inputs are ready. Each local dashboard opening becomes usable within 5 seconds. Every cell selection updates its details and charts within 1 second. Report setup and download times separately. |
| T18 | Invalid input and failure handling Test a missing required file, an altered checksum, a duplicate cell and month record, a geometry mismatch and an unavailable catalogue. | Every invalid package is rejected with a clear reason before new results are issued. A failed catalogue request is reported as unavailable or unknown, not as zero coverage. No case creates fabricated observations or presents old results as a successful new run. Keep all five error records. |
| T19 | Hyperspectral status and evidence Test the workflow without EnMAP input. If real pixels are available, also test the completed analysis path. | Without valid input, the dashboard states that EnMAP was not analysed and the Sentinel-2 baseline remains unchanged. A completed EnMAP claim requires analysis_complete status, a real Zankalon scene identifier, acquisition date and derived spectral output. A Tanager scene outside Zankalon is labelled as a method demonstration. |
| T20 | Responsible reporting Inspect the dashboard, result notes, metadata and final archive. | The files identify sources, dates, settings and input checksums. They state that thresholds are exploratory and flags need field investigation. They contain no unsupported accuracy, yield-loss or confirmed degradation claims. The public archive contains no credentials or private EnMAP pixel files. |

# 8 Acceptance decision and evidence

Accept the core pilot only when every core criterion passes and no unresolved defect changes a calculation, category, location or explanation. Correct failed criteria and repeat the affected tests. A Blocked criterion is not a pass. The real EnMAP analysis branch may remain Blocked without preventing core acceptance, provided the unavailable-data behaviour in T19 passes and the extension is not presented as complete.

Keep one test record per criterion containing the input version, expected result, actual result, status, evidence filename, tester and date. Numerical tests require calculation or comparison records. Interface tests require screenshots and task observations. Timing tests require individual timings. Record the final decision and any remaining limitations.
