# Manufacturing CAD Intelligence

End-to-end Databricks demo that turns engineering drawings (PDF) into governed bills of materials, forecasts part demand across a European plant network, and serves it all through a Databricks App backed by Unity Catalog, Lakebase and Genie.

All data is synthetic and for demonstration only.

For reviewers:

* [EVIDENCE.md](EVIDENCE.md): captured run output. It covers table row counts, BOM accuracy against ground truth, CAD label and vision-fallback checks, forecast quality, and the app's deployment status.
* [BUILD_LOG.md](BUILD_LOG.md): how the project was built with an AI assistant. It covers who decided what, nine concrete moments where the AI changed the outcome, and the guardrails used.

## KPIs and owners

Each KPI has one accountable owner and drives a recurring decision. Demo values come from [EVIDENCE.md](EVIDENCE.md) and run on synthetic data. They show that the metric can be computed; they are not customer results.

| KPI | Definition | Accountable owner | Decision it drives | Cadence | Demo value |
| --- | --- | --- | --- | --- | --- |
| CAD extraction accuracy | Share of BOM lines (part, qty, material, revision) extracted correctly from drawing PDFs | Head of Engineering / PLM | Whether an extracted BOM can be released without manual re-entry | Per drawing release | 72 / 72 lines (100%) |
| Forecast error (WAPE) | Weighted absolute % error of forecast vs actual part consumption, per plant and part | Demand Planning Lead | Safety-stock levels and forecast overrides | Monthly S&OP | 2.05% (vs the reference forecast; no actuals yet for the forecast months) |
| Projected shortage quantity | Units by which forecast demand exceeds the remaining stock on hand, per plant, part and month (open purchase orders are not yet netted) | Plant Operations Manager | Expediting, moving stock between plants, production re-sequencing | Weekly | 4,086 units across 119 of 216 plant-part-months |
| Procurement planning lead time | Time from a drawing revision being released to purchase orders being placed for its new or changed parts | VP Procurement | Supplier order timing; reduction of spot buys and expedite fees | Monthly | Not measured in the demo; baseline it in a pilot from PLM release dates and ERP PO timestamps |

## Architecture

| Layer | Technology | Assets |
| --- | --- | --- |
| Storage and governance | Unity Catalog (`gabi_bosch_sandbox_catalog.cad_intelligence`), UC Volume `raw_drawings` | seed CSVs, PDF drawings |
| Document AI | `ai_parse_document`, `ai_extract` | `02_pdf_ai_extract.sql`, `02b_normalize_extraction` |
| Forecasting | PySpark | `03_forecast` |
| Streaming ingestion | Lakeflow Spark Declarative Pipelines | `07_lakeflow_consumption.py` |
| Natural-language analytics | Genie | `04_genie_queries.sql` |
| Operational store | Lakebase Postgres | `lakebase_schema.sql`, `manufacturing-cad-app/lakebase.py` |
| Application | Databricks Apps (Streamlit) | `manufacturing-cad-app/` |

## Repository layout

```
01_setup_and_seed.py          Create schema/volume and seed Delta tables from CSVs
02_pdf_ai_extract.sql         Parse PDFs and extract drawing BOMs with AI Functions
02b_normalize_extraction.py   Normalize AI extraction output into extracted_bom
02c_extract_cad_labels.py     Extract CAD text-layer labels/callouts with page coordinates into cad_annotations
02d_vision_fallback.py        Optional multimodal extraction for rasterized labels (needs a vision endpoint)
03_forecast.py                3-month part consumption and shortage forecast
04_genie_queries.sql          Verified example queries for the Genie space
05_load_full_dataset.sql      Note: reference outputs are not loaded to production
06_validation.sql             Post-deployment row-count validation
07_lakeflow_consumption.py    Lakeflow pipeline source (Auto Loader bronze/silver)
08_cad_annotations_validation.sql  Validation queries for cad_annotations (run after 02c)
EVIDENCE.md                   Captured execution evidence and validation results
BUILD_LOG.md                  AI-assisted build log: decisions, moments, guardrails
lakebase_schema.sql           Lakebase document_review table DDL
manufacturing-cad-app/        Databricks App (Streamlit)
  app.py                      UI: overview, upload and review, analytics, forecast, plant map, CAD labels, Genie
  lakebase.py                 Lakebase connection with OAuth token per connection
  app.yaml                    App command and environment / resource bindings
  requirements.txt            Python dependencies
```

## Run order

1. `01_setup_and_seed` - upload `seed/*.csv` and `incoming/*.pdf` to the `raw_drawings` volume first.
2. `02_pdf_ai_extract.sql` on a serverless SQL warehouse.
3. `02b_normalize_extraction`.
4. `02c_extract_cad_labels` (optionally `02d_vision_fallback`), then `08_cad_annotations_validation.sql`.
5. `03_forecast`.
6. Create a Genie space over `plants`, `parts`, `monthly_consumption`, `extracted_bom`, `part_forecast`.
7. Deploy the app (below).

## Deploying the app

App resources expected by `app.yaml`:

| Resource key | Type | Permission |
| --- | --- | --- |
| `sql-warehouse` | SQL warehouse | Can use |
| `extraction_job` | Job | Can manage run |
| `genie-space` | Genie space | Can manage |
| `postgres` | Lakebase database | Can connect and create |
| `drawings_volume` | UC volume | Write volume |

The app service principal also needs Unity Catalog read access:

```sql
GRANT USE CATALOG ON CATALOG gabi_bosch_sandbox_catalog TO `<app-service-principal-id>`;
GRANT USE SCHEMA, SELECT ON SCHEMA gabi_bosch_sandbox_catalog.cad_intelligence TO `<app-service-principal-id>`;
```

Notes:

* The app connects to Lakebase as its own service principal; do not set `PGUSER`/`PGPASSWORD`.
* The service principal cannot create objects in the Postgres `public` schema, so the app creates and owns the `cad_app` schema.

Deploy:

```
databricks apps deploy manufacturing-cad-intelligence --source-code-path <workspace-path-to>/manufacturing-cad-app
```
