-- Execute in the Lakebase PostgreSQL SQL editor, not a Databricks SQL warehouse.
CREATE TABLE IF NOT EXISTS document_review (
  document_id TEXT PRIMARY KEY, file_name TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('SUBMITTED','NEEDS_REVIEW','APPROVED','REJECTED')),
  notes TEXT DEFAULT '', updated_at TIMESTAMPTZ DEFAULT now());
CREATE INDEX IF NOT EXISTS document_review_status_idx ON document_review(status);
