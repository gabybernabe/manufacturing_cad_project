# Lakeflow Spark Declarative Pipeline source. Configure a pipeline with this file as source.
from pyspark import pipelines as dp
from pyspark.sql import functions as F
@dp.table(name='consumption_lakeflow_bronze', comment='Auto Loader ingestion of synthetic consumption CSV')
def consumption_lakeflow_bronze():
    return (spark.readStream.format('cloudFiles')
            .option('cloudFiles.format','csv').option('header','true')
            .option('cloudFiles.inferColumnTypes','true')
            .load('/Volumes/manufacturing_demo/cad_intelligence/raw_drawings/seed/monthly_consumption.csv'))
@dp.table(name='consumption_lakeflow_silver')
def consumption_lakeflow_silver():
    return (spark.readStream.table('consumption_lakeflow_bronze')
            .withColumn('month',F.to_date('month')))
