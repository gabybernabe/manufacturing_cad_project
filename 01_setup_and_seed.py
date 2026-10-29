# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "6"
# ///
# DBTITLE 1,Setup catalog, schema and volume
from pyspark.sql import functions as F
CATALOG='gabi_bosch_sandbox_catalog'; SCHEMA='cad_intelligence'; BASE=f'{CATALOG}.{SCHEMA}'
spark.sql(f'CREATE SCHEMA IF NOT EXISTS {BASE}')
spark.sql(f'CREATE VOLUME IF NOT EXISTS {BASE}.raw_drawings')
ROOT=f'/Volumes/{CATALOG}/{SCHEMA}/raw_drawings'
print('UPLOAD_TO=',ROOT)

# COMMAND ----------

# Upload dataset/seed/*.csv -> ROOT/seed/
# Upload dataset/pdf_drawings/*.pdf -> ROOT/incoming/
# Upload dataset/expected_outputs/*.csv -> ROOT/expected_outputs/
TABLES=['parts','plants','monthly_consumption','drawing_registry','part_master_extended',
        'plant_master_extended','purchase_orders','inventory_snapshot']
for name in TABLES:
    df=(spark.read.option('header',True).option('inferSchema',True)
        .csv(f'{ROOT}/seed/{name}.csv'))
    for col in ['month','order_month','document_date','as_of_date']:
        if col in df.columns: df=df.withColumn(col,F.to_date(col))
    df.write.format('delta').mode('overwrite').option('overwriteSchema','true').saveAsTable(f'{BASE}.{name}')
    print('SEEDED',name,df.count())

# COMMAND ----------

# Ground truth is held in a separate table and NEVER substituted for model extraction.
for name in ['extracted_bom_ground_truth','part_forecast','plant_monthly_map']:
    df=(spark.read.option('header',True).option('inferSchema',True)
        .csv(f'{ROOT}/expected_outputs/{name}.csv'))
    if 'month' in df.columns: df=df.withColumn('month',F.to_date('month'))
    dest='expected_'+name
    df.write.format('delta').mode('overwrite').option('overwriteSchema','true').saveAsTable(f'{BASE}.{dest}')
    print('REFERENCE_ONLY',dest,df.count())

# COMMAND ----------

spark.sql(f'''CREATE TABLE IF NOT EXISTS {BASE}.extracted_bom (
 drawing_id STRING, revision STRING, source_file STRING, part_id STRING,
 description STRING, material STRING, qty INT) USING DELTA''')
spark.sql(f'''CREATE TABLE IF NOT EXISTS {BASE}.part_forecast (
 month DATE, plant_id STRING, part_id STRING, forecast_consumed_qty INT,
 projected_purchase_qty INT, projected_shortage_qty INT) USING DELTA''')
print('SETUP_COMPLETE')