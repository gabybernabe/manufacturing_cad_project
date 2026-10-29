-- Add plants, parts, monthly_consumption, extracted_bom, part_forecast to a Genie space.
-- Define: projected_purchase_qty = modeled requirement without future receipts, NOT actual POs.
-- Verified question: What is projected procurement by plant next month?
SELECT f.month,p.plant_name,SUM(f.projected_purchase_qty) AS projected_parts_to_buy
FROM gabi_bosch_sandbox_catalog.cad_intelligence.part_forecast f
JOIN gabi_bosch_sandbox_catalog.cad_intelligence.plants p USING(plant_id)
WHERE f.month=(SELECT MIN(month) FROM gabi_bosch_sandbox_catalog.cad_intelligence.part_forecast)
GROUP BY 1,2 ORDER BY 3 DESC;
-- Verified question: Which drawings use bearing BRG-6205?
SELECT drawing_id,revision,source_file,part_id,qty
FROM gabi_bosch_sandbox_catalog.cad_intelligence.extracted_bom
WHERE part_id='BRG-6205';
