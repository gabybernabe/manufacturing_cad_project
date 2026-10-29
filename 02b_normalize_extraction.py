# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "6"
# ///
# DBTITLE 1,Normalize extraction into BOM table
import json
from pyspark.sql import Row, functions as F
BASE='gabi_bosch_sandbox_catalog.cad_intelligence'
records=[]
for row in spark.sql(f'SELECT source_file, to_json(extracted) AS payload FROM {BASE}.ai_extraction_raw').toLocalIterator():
    data=json.loads(row.payload or '{}')
    response=data.get('response') or {}
    def val(x): return x.get('value') if isinstance(x,dict) and 'value' in x else x
    drawing=val(response.get('drawing_id')); revision=val(response.get('revision'))
    if data.get('error_message'): print('EXTRACTION_ERROR',row.source_file,data['error_message'])
    for p in val(response.get('parts')) or []:
        if not isinstance(p,dict): continue
        pid=val(p.get('part_id')); qty=val(p.get('qty'))
        if not pid or qty is None: continue
        records.append(Row(drawing_id=str(drawing or ''),revision=str(revision or ''),source_file=row.source_file,
                           part_id=str(pid),description=str(val(p.get('description')) or ''),
                           material=str(val(p.get('material')) or ''),qty=int(qty)))
if records:
    spark.createDataFrame(records).withColumn('qty',F.col('qty').cast('int')).dropDuplicates(['source_file','part_id']).write.mode('overwrite').saveAsTable(f'{BASE}.extracted_bom')
print('BOM_ROWS=',len(records))