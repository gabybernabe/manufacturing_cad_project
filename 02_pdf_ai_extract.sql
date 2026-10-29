-- Databricks SQL notebook / serverless SQL warehouse. Configure AI Functions region support first.
-- Reads raw PDF bytes from UC Volume and extracts title block parsing.
-- First run this on the 3 synthetic PDFs; large real CAD drawings require review.
CREATE OR REPLACE TABLE gabi_bosch_sandbox_catalog.cad_intelligence.parsed_documents AS
SELECT path AS source_file,
       ai_parse_document(content, map('version','2.0')) AS parsed
FROM read_files('/Volumes/gabi_bosch_sandbox_catalog/cad_intelligence/raw_drawings/incoming/',
                format => 'binaryFile', fileNamePattern => '*.pdf');

CREATE OR REPLACE TABLE gabi_bosch_sandbox_catalog.cad_intelligence.ai_extraction_raw AS
SELECT source_file,
       ai_extract(parsed,
         '{"drawing_id":{"type":"string","description":"Engineering drawing identifier from title block"},
           "revision":{"type":"string","description":"Drawing revision"},
           "parts":{"type":"array","items":{"type":"object","properties":{
             "part_id":{"type":"string","description":"Exact part identifier in BOM"},
             "description":{"type":"string"},
             "material":{"type":"string"},
             "qty":{"type":"integer","description":"Quantity per assembly"}}}}}',
         map('version','2.1','mode','precision',
             'instructions','Extract only explicitly labeled parts from BOM tables and callouts. Do not invent dimensions or identifiers.')) AS extracted
FROM gabi_bosch_sandbox_catalog.cad_intelligence.parsed_documents;


