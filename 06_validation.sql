-- Run after deployment and save actual query output as text.
SELECT 'parts' AS table_name, count(*) AS rows FROM manufacturing_demo.cad_intelligence.parts
UNION ALL SELECT 'plants', count(*) FROM manufacturing_demo.cad_intelligence.plants
UNION ALL SELECT 'drawings', count(*) FROM manufacturing_demo.cad_intelligence.drawing_registry
UNION ALL SELECT 'consumption', count(*) FROM manufacturing_demo.cad_intelligence.monthly_consumption
UNION ALL SELECT 'purchases', count(*) FROM manufacturing_demo.cad_intelligence.purchase_orders
UNION ALL SELECT 'extracted_bom', count(*) FROM manufacturing_demo.cad_intelligence.extracted_bom
UNION ALL SELECT 'forecast', count(*) FROM manufacturing_demo.cad_intelligence.part_forecast;
SELECT * FROM manufacturing_demo.cad_intelligence.extracted_bom LIMIT 10;
SELECT * FROM manufacturing_demo.cad_intelligence.part_forecast LIMIT 10;
