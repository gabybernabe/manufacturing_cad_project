# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "6"
# ///
# DBTITLE 1,Normalize extraction into BOM table
import json
from pyspark.sql import Row, Window, functions as F
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
    bom=spark.createDataFrame(records).withColumn('qty',F.col('qty').cast('int'))
    # One BOM line per drawing revision and part: a re-uploaded PDF of a known drawing revision
    # (e.g. a UUID-named app upload of CAD-0007) must not duplicate lines.
    # Prefer the file registered in drawing_registry, then the lowest source_file for determinism.
    reg=spark.table(f'{BASE}.drawing_registry').select('drawing_id','revision',F.col('source_file').alias('registry_file'))
    w=Window.partitionBy('drawing_id','revision','part_id').orderBy(
        F.when(F.element_at(F.split('source_file','/'),-1)==F.col('registry_file'),0).otherwise(1),'source_file')
    deduped=(bom.join(reg,['drawing_id','revision'],'left')
             .withColumn('_rn',F.row_number().over(w)).filter('_rn=1')
             .select('drawing_id','revision','source_file','part_id','description','material','qty'))
    deduped.write.mode('overwrite').saveAsTable(f'{BASE}.extracted_bom')
    written=spark.table(f'{BASE}.extracted_bom').count()
    print('BOM_ROWS_RAW=',len(records),'| BOM_ROWS_WRITTEN=',written,'| DUPLICATES_DROPPED=',len(records)-written)
else:
    print('BOM_ROWS= 0')