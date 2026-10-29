-- NEW: execute after 02c. Save actual query output in evidence/.
SELECT label_type, review_status, count(*) AS labels
FROM manufacturing_demo.cad_intelligence.cad_annotations
GROUP BY label_type, review_status ORDER BY label_type, review_status;

SELECT drawing_id, label_text AS callout, matched_part_id, page_number, x0, y0, x1, y1
FROM manufacturing_demo.cad_intelligence.cad_annotations
WHERE label_type='component_callout' ORDER BY drawing_id, label_text LIMIT 100;

SELECT a.drawing_id, a.label_text, a.matched_part_id,
       CASE WHEN b.part_id IS NOT NULL THEN 'FOUND_IN_EXTRACTED_BOM' ELSE 'REVIEW_MATCH' END AS match_check
FROM manufacturing_demo.cad_intelligence.cad_annotations a
LEFT JOIN manufacturing_demo.cad_intelligence.extracted_bom b
 ON a.drawing_id=b.drawing_id AND a.matched_part_id=b.part_id
WHERE a.label_type='component_callout';
