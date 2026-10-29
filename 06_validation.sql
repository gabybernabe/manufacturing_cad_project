-- Run after deployment and save actual query output as text.
SELECT 'parts' AS table_name, count(*) AS rows FROM gabi_bosch_sandbox_catalog.cad_intelligence.parts
UNION ALL SELECT 'plants', count(*) FROM gabi_bosch_sandbox_catalog.cad_intelligence.plants
UNION ALL SELECT 'drawings', count(*) FROM gabi_bosch_sandbox_catalog.cad_intelligence.drawing_registry
UNION ALL SELECT 'consumption', count(*) FROM gabi_bosch_sandbox_catalog.cad_intelligence.monthly_consumption
UNION ALL SELECT 'purchases', count(*) FROM gabi_bosch_sandbox_catalog.cad_intelligence.purchase_orders
UNION ALL SELECT 'extracted_bom', count(*) FROM gabi_bosch_sandbox_catalog.cad_intelligence.extracted_bom
UNION ALL SELECT 'forecast', count(*) FROM gabi_bosch_sandbox_catalog.cad_intelligence.part_forecast;
SELECT * FROM gabi_bosch_sandbox_catalog.cad_intelligence.extracted_bom LIMIT 10;
SELECT * FROM gabi_bosch_sandbox_catalog.cad_intelligence.part_forecast LIMIT 10;
