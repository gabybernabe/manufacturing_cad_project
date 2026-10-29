# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "6"
# ///
# DBTITLE 1,Forecast part consumption and shortages
from pyspark.sql import functions as F, Window
from dateutil.relativedelta import relativedelta
from datetime import datetime
BASE='gabi_bosch_sandbox_catalog.cad_intelligence'
usage=spark.table(f'{BASE}.monthly_consumption')
w=Window.partitionBy('plant_id','part_id').orderBy(F.col('month').desc())
last3=usage.withColumn('rn',F.row_number().over(w)).filter('rn <= 3')
agg=last3.groupBy('plant_id','part_id').agg(
    F.round(F.avg('consumed_qty')).cast('int').alias('forecast_consumed_qty'),
    F.max(F.when(F.col('rn')==1,F.col('stock_on_hand'))).alias('stock_on_hand'))
last=usage.agg(F.max('month')).first()[0]
rows=[]
for r in agg.toLocalIterator():
    remaining=int(r.stock_on_hand or 0)
    for i in range(1,4):
        month=(last+relativedelta(months=i)).replace(day=1)
        need=int(r.forecast_consumed_qty or 0)
        shortage=max(0,need-remaining)
        remaining=max(0,remaining-need)
        rows.append((month,r.plant_id,r.part_id,need,shortage,shortage))
cols=['month','plant_id','part_id','forecast_consumed_qty','projected_purchase_qty','projected_shortage_qty']
spark.createDataFrame(rows,cols).withColumns({c:F.col(c).cast('int') for c in cols[3:]}).write.mode('overwrite').saveAsTable(f'{BASE}.part_forecast')
print('FORECAST_ROWS=',len(rows),'LAST_HISTORICAL_MONTH=',last)