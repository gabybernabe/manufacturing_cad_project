# Build Log: How AI Changed the Build

This project was built in a Databricks workspace with Genie Code, the in-product AI assistant, working alongside me. The assistant had direct access to the workspace: it could read notebooks, query Unity Catalog, inspect the app, and run Git. It did not just suggest code; it ran checks against live data and reported what it found.

This log records specific moments where that changed the outcome, including where the AI was wrong or was stopped. Numbers refer to [EVIDENCE.md](EVIDENCE.md).

## How the work was split

| I decided | The AI did |
| --- | --- |
| Problem scope, architecture, and which Databricks services to use | Diagnosed failures from error messages, table schemas and live data |
| Keeping `expected_*` ground-truth tables out of production paths | Wrote and changed code in notebooks, the app and SQL files |
| Interpretable forecasting over a complex model | Ran read-only dry runs before any change that overwrites a table |
| Text-layer extraction first, multimodal as a fallback | Checked results with a second, independent query before reporting them |
| When to overwrite tables, deploy, commit and push | Committed and pushed only when I asked |

## Moments where the AI changed the outcome

### 1. Catalog permissions blocked setup on the first run

* **Situation:** `01_setup_and_seed` failed on `CREATE CATALOG manufacturing_demo`, even with `IF NOT EXISTS`.
* **What the AI did:** It read the error, confirmed I had no CREATE CATALOG privilege on the metastore, and found a catalog where I had ALL PRIVILEGES (`gabi_bosch_sandbox_catalog`). It moved the schema, volume and every table reference there.
* **Why it mattered:** I didn't have to wait for an admin grant to create a new catalog.

### 2. Type mismatches between Python and Delta

* **Situation:** Writes to `extracted_bom` and `part_forecast` failed against their INT columns.
* **What the AI did:** It traced the cause to Spark inferring Python `int` values in `Row` objects as `bigint`, and added explicit `cast('int')` before each write.
* **Why it mattered:** The table schemas stayed as designed instead of being widened to fit the bug.

### 3. The deployed app couldn't log in to Lakebase

* **Situation:** The app worked for me but failed after deployment with "OAuth: User is not authorized".
* **What the AI did:** It found that `lakebase.py` hardcoded `PGUSER` to my email, while the deployed app authenticates as its own service principal. It changed the code to read the user from `current_user.me()`. When the service principal then couldn't create tables in the Postgres `public` schema, the app was changed to create and own its own `cad_app` schema, set through `search_path`.
* **Why it mattered:** This is a common deploy-time failure in Databricks Apps. Finding the root cause, rather than granting broader rights, kept the app on least privilege. The Unity Catalog grants were left for me to run, since the AI's own grant attempts were blocked.

### 4. Testing the Streamlit app without clicking through it

* **What the AI did:** It smoke-tested `app.py` with Streamlit's `AppTest` against parquet snapshots of the real tables before each deployment.
* **Why it mattered:** All seven pages were exercised on real data shapes before deployment, without manually clicking through the deployed app.

### 5. A missing package traced to a commented-out line

* **Situation:** `02d_vision_fallback` failed with `ModuleNotFoundError: fitz`.
* **What the AI did:** It found that the install line in Cell 1 was commented out, and that the version range wasn't quoted, so the shell would treat `<2` as a redirect.
* **Where the AI was stopped:** Its first fix put `%pip install` inside the analysis cell. That run was blocked because it could restart Python mid-session. The AI reverted the change and moved the install to its own cell. It also removed `databricks-sdk` from the install, since that package comes with the runtime.

### 6. Choosing and testing a vision model

* **What the AI did:** It listed the workspace's serving endpoints and picked one that accepts images (`databricks-claude-sonnet-4-6`). It made it the default while keeping an environment-variable override, then ran one page (2,639 tokens) before scaling.
* **Why it mattered:** The fallback was proven on one drawing at a known cost before any batch run.

### 7. A false positive in the AI's own comparison code

* **Situation:** The first comparison between vision and text-layer labels reported 6 partial matches.
* **What the AI did:** It noticed that bare callout numbers such as "01" were matching inside dates and drawing IDs. It excluded callouts from the partial check and re-ran: 4 real partial matches, 4 labels found only by vision, and 0 found only by the text layer.
* **Why it mattered:** Without this catch, the headline numbers would have overstated how much the two methods agree.

### 8. Writing the evidence found two real bugs

I asked for a document of live table counts. While building it, the AI cross-checked counts against ground truth instead of copying them, and found:

* **Duplicate drawing:** `extracted_bom` had 78 rows for 72 ground-truth lines. The cause was an app upload (`d34a69f7-...pdf`) of CAD-0007 revision B, which duplicated 6 BOM lines and 22 CAD labels.
* **Stale catalog name:** both validation SQL files still pointed at `manufacturing_demo`, which doesn't exist. The validation scripts would have failed for any reviewer who ran them.

The AI fixed both:

* `02b` now keeps one BOM line per `(drawing_id, revision, part_id)` and prefers the registered file.
* `02c` skips duplicate files for the same drawing revision.
* Before overwriting anything, it dry-ran both changes read-only and confirmed 78 to 72 BOM lines with all 72 still correct, and 278 to 256 labels.
* After I approved, it re-ran both and checked the saved tables.

### 9. KPI definitions checked against the code

* **Situation:** I asked for a KPI owner table in the README.
* **What the AI did:** It read `03_forecast` before writing the definitions and corrected two of its own drafts:
  * Projected shortage doesn't yet subtract open purchase orders.
  * The 2.05% WAPE is measured against a reference forecast, not actuals.
* **Why it mattered:** The README now describes what the code actually computes.

## Guardrails that shaped the workflow

* **Read before write:** table schemas, notebook code and app state were inspected before every change.
* **Dry run before overwrite:** changes to `extracted_bom` and `cad_annotations` were first computed without writing, and the result was compared with ground truth.
* **The human controls irreversible steps:** table overwrites, Unity Catalog grants, deployments and Git pushes happened only when I asked.
* **Blocked actions stayed blocked:** when a step was refused (installing a package inside an analysis cell, submitting an ad-hoc job run), the AI changed approach instead of retrying the same step.

## What I would do differently

* **Commit notebooks with outputs:** commit them as `.ipynb` with outputs from the start, so execution evidence lives next to the code.
* **Block re-uploads in the app:** reject uploads of a drawing revision that already exists, so duplicates can't get in at all.
* **Fix the shortage KPI:** net open purchase orders into projected shortage before using it in a pilot.
