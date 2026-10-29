# Execution Evidence

Outputs captured from the live workspace by read-only queries against `gabi_bosch_sandbox_catalog.cad_intelligence` and the Databricks Apps API.

* Captured: 2026-10-29 15:44 UTC (Spark `current_timestamp()`). Updated 2026-10-29 16:48 UTC after re-running `02b` and `02c` with de-duplication (sections 1-3)
* Workspace: `fevm-gabi-bosch-sandbox` (7474657324530298)
* All data is synthetic. Tables prefixed `expected_` are held-out reference outputs used only for validation. By design, the pipeline and the app don't read them.

## 1. Pipeline output: table row counts

| Layer | Table | Rows | Produced by |
| --- | --- | --- | --- |
| Seed | `plants` | 6 | `01_setup_and_seed` |
| Seed | `parts` | 12 | `01_setup_and_seed` |
| Seed | `plant_master_extended` | 6 | `01_setup_and_seed` |
| Seed | `part_master_extended` | 12 | `01_setup_and_seed` |
| Seed | `drawing_registry` | 12 | `01_setup_and_seed` |
| Seed | `monthly_consumption` | 1,512 | `01_setup_and_seed` (2025-01 to 2026-09, 6 plants x 12 parts x 21 months) |
| Seed | `purchase_orders` | 1,512 | `01_setup_and_seed` |
| Seed | `inventory_snapshot` | 72 | `01_setup_and_seed` |
| Document AI | `parsed_documents` | 13 | `02_pdf_ai_extract.sql` (`ai_parse_document`) |
| Document AI | `ai_extraction_raw` | 13 | `02_pdf_ai_extract.sql` (`ai_extract`) |
| Document AI | `extracted_bom` | 72 | `02b_normalize_extraction` (Delta version 4, 16:47 UTC) |
| CAD labels | `cad_annotations` | 256 | `02c_extract_cad_labels` (PyMuPDF text layer; Delta version 1, 16:47 UTC) |
| Forecast | `part_forecast` | 216 | `03_forecast` (2026-10 to 2026-12, 6 plants x 12 parts x 3 months) |
| Reference (validation only) | `expected_extracted_bom_ground_truth` | 72 | synthetic ground truth |
| Reference (validation only) | `expected_part_forecast` | 216 | synthetic ground truth |
| Reference (validation only) | `expected_plant_monthly_map` | 126 | synthetic ground truth |

13 PDFs were parsed: the 12 registry drawings plus one file uploaded through the app (`d34a69f7-54f6-47ad-b182-e3ab2cb4eebd.pdf`). That upload is a copy of CAD-0007 revision B, so `02b` and `02c` keep one source file per drawing revision (the registered file) and skip it.

Re-run output (2026-10-29 16:47 UTC):

```
02b: BOM_ROWS_RAW= 78 | BOM_ROWS_WRITTEN= 72 | DUPLICATES_DROPPED= 6
02c: DUPLICATE_FILES_SKIPPED= ['d34a69f7-54f6-47ad-b182-e3ab2cb4eebd.pdf'] | LABELS_DROPPED= 22
02c: CAD_ANNOTATIONS_TOTAL= 256
```

The cell code of the repo notebooks was executed on serverless compute, and the result was verified by querying the saved tables: 72 rows = 72 unique drawing-part pairs; 0 rows from the duplicate file in either table.

## 2. BOM extraction accuracy (`ai_extract` vs ground truth)

Joined `expected_extracted_bom_ground_truth` to `extracted_bom` on `(drawing_id, part_id)`.

| Check | Result |
| --- | --- |
| Drawings extracted | 12 / 12 |
| Ground-truth BOM lines found | 72 / 72 (100%) |
| Quantity correct | 72 / 72 (100%) |
| Material correct (case/whitespace-insensitive) | 72 / 72 (100%) |
| Revision correct | 72 / 72 (100%) |
| Extracted lines not in ground truth | 0 |

## 3. CAD label extraction (`02c_extract_cad_labels`)

Output of the de-duplicated run on 2026-10-29 16:47 UTC:

```
CAD_ANNOTATIONS_TOTAL= 256
+-----------------------+-------------+-----+
|label_type             |review_status|count|
+-----------------------+-------------+-----+
|component_callout      |MATCHED      |72   |
|dimension              |NEEDS_REVIEW |34   |
|technical_specification|NEEDS_REVIEW |102  |
|tolerance_or_dimension |NEEDS_REVIEW |48   |
+-----------------------+-------------+-----+
```

| Check | Result |
| --- | --- |
| Callouts with a matched part ID | 72 / 72 |
| Callout part IDs present in `extracted_bom` for the same drawing (`08_cad_annotations_validation.sql`) | 72 / 72 `FOUND_IN_EXTRACTED_BOM` |
| Source files covered | 12 (one per registered drawing) |

The previous run (14:04 UTC) had 278 labels and 78 callouts. The extra 22 labels and 6 callouts came from the duplicate CAD-0007 upload.

Every callout on the drawing has page coordinates (`x0, y0, x1, y1`). The two extraction methods (text-layer coordinates and `ai_extract`) independently agree on every callout-to-part link.

## 4. Multimodal fallback (`02d_vision_fallback`)

One-page test on `CAD-0001_axis_drive_module_revB.pdf` with `databricks-claude-sonnet-4-6` (2,639 tokens). 17 labels were returned and compared with the 21 labels 02c extracted for the same page:

| Outcome | Labels | Notes |
| --- | --- | --- |
| Exact match | 9 | 6 callouts, 2 tolerances, drawing/revision line |
| Partial match | 4 | Full BOM rows from vision. 02c captured only fragments such as `Ø25 x 120 mm` |
| Only from vision | 4 | `SECTION A-A 1:2`, title block, MTR-450 and GEA-042 BOM rows |
| Only from 02c | 0 | All 02c labels are contained in vision labels |
| Callout-to-part agreement | 6 / 6 | |

The vision output has not been merged into `cad_annotations`.

## 5. Forecast quality (`part_forecast` vs `expected_part_forecast`)

216 rows: 6 plants x 12 parts x 3 months (2026-10 to 2026-12).

| Metric | Result |
| --- | --- |
| Mean expected monthly consumption | 40.9 units |
| Weighted absolute percentage error (WAPE), consumption | 2.05% |
| Mean absolute error, consumption | 0.84 units |
| Max absolute error | 3 units |
| Forecasts within +/-1 unit | 175 / 216 (81.0%) |
| Exact consumption match | 77 / 216 (35.6%) |
| Shortage flag (shortage > 0) agrees with reference | 183 / 216 (84.7%) |
| Exact shortage quantity match | 65 / 216 (30.1%) |
| Plant-part-months with a projected shortage | 119 / 216 |
| Total projected shortage | 4,086 units |

## 6. Databricks App deployment

From `databricks apps get manufacturing-cad-intelligence`:

| Field | Value |
| --- | --- |
| App status | RUNNING ("App is running") |
| Compute | ACTIVE, MEDIUM |
| Active deployment | `01f1d3ab2a2812fdb57df5d94d9839eb`, SUCCEEDED ("App started successfully"), 2026-10-29 15:12 UTC |
| Source path | `febar-manufacturing-intelligence-repo/manufacturing-cad-app` (this repo) |
| Bound resources | SQL warehouse (CAN_USE), extraction job (CAN_MANAGE_RUN), Genie space "Manufacturing Parts and Inventory Management" (CAN_MANAGE), Lakebase `manufacturing-cad-operations/production` (CAN_CONNECT_AND_CREATE), volume `raw_drawings` (WRITE_VOLUME) |
| Runs as | App service principal `app-3lwc2b` |

## Known issues found while capturing this evidence

* **Duplicate drawing from an app upload (fixed).** `d34a69f7-54f6-47ad-b182-e3ab2cb4eebd.pdf` is a re-upload of CAD-0007 revision B. It had added 6 duplicate `extracted_bom` lines and 22 duplicate `cad_annotations` labels (6 of them callouts). `02b` now de-duplicates on `(drawing_id, revision, part_id)` and `02c` keeps one source file per drawing revision, preferring the file in `drawing_registry`. After the re-run, `extracted_bom` has 72 rows and `cad_annotations` has 256. Still open: the app doesn't yet warn when someone uploads a revision that already exists.
* **Stale catalog name in validation scripts (fixed).** `06_validation.sql` and `08_cad_annotations_validation.sql` referenced `manufacturing_demo`, which doesn't exist. They now use `gabi_bosch_sandbox_catalog`. Their row counts match section 1, and the last query in `08` returns 72 rows, all `FOUND_IN_EXTRACTED_BOM` (before de-duplication it returned 90).
* **Forecast exact-match rate is low (35.6%), but the error is small.** WAPE is 2.05% and the largest miss is 3 units, so most misses are small: 98 of the 139 non-exact forecasts are off by exactly 1 unit.

## How to reproduce

Run the notebooks in the order given in `README.md`, then the queries in `06_validation.sql` and `08_cad_annotations_validation.sql`.
