# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "6"
# ///
# NEW 02c: extract positioned text labels from PDF vector/text layers.
# Run on serverless notebook compute. Install PyMuPDF in notebook environment if needed.
# %pip install PyMuPDF>=1.24,<2

# COMMAND ----------

# DBTITLE 1,Extract CAD labels into cad_annotations
# MAGIC %pip install "PyMuPDF>=1.24,<2"
# MAGIC import fitz, re, json, os
# MAGIC from pathlib import Path
# MAGIC from pyspark.sql import types as T
# MAGIC BASE = "gabi_bosch_sandbox_catalog.cad_intelligence"
# MAGIC PDF_ROOT = "/Volumes/gabi_bosch_sandbox_catalog/cad_intelligence/raw_drawings/incoming"
# MAGIC
# MAGIC schema = T.StructType([
# MAGIC     T.StructField('drawing_id',T.StringType()),T.StructField('source_file',T.StringType()),
# MAGIC     T.StructField('page_number',T.IntegerType()),T.StructField('label_text',T.StringType()),
# MAGIC     T.StructField('label_type',T.StringType()),T.StructField('x0',T.DoubleType()),
# MAGIC     T.StructField('y0',T.DoubleType()),T.StructField('x1',T.DoubleType()),
# MAGIC     T.StructField('y1',T.DoubleType()),T.StructField('page_width',T.DoubleType()),
# MAGIC     T.StructField('page_height',T.DoubleType()),T.StructField('matched_part_id',T.StringType()),
# MAGIC     T.StructField('extraction_method',T.StringType()),T.StructField('review_status',T.StringType())
# MAGIC ])
# MAGIC
# MAGIC def classify(text, y, height):
# MAGIC     s=text.strip()
# MAGIC     # Standalone numbered callout near the drawing, not the BOM table
# MAGIC     if re.fullmatch(r'0?[1-9]|[1-9][0-9]',s) and y < height*0.60: return 'component_callout'
# MAGIC     if re.search(r'(?:\+/-|±|\u00b1)',s) and re.search(r'\d',s): return 'tolerance_or_dimension'
# MAGIC     if re.search(r'(?:Ø|⌀|\bM\d+(?:[xX ]|$)|\bG1/\d|\bR\d)',s): return 'technical_specification'
# MAGIC     if re.search(r'\b(?:mm|cm|deg|°)\b',s,re.I) and re.search(r'\d',s): return 'dimension'
# MAGIC     return None
# MAGIC
# MAGIC def bom_lookup(page):
# MAGIC     # Demo drawing format: each BOM item is followed by a part identifier on next line.
# MAGIC     text=page.get_text('text')
# MAGIC     section=text.split('BILL OF MATERIALS (BOM)',1)
# MAGIC     if len(section)<2:return {}
# MAGIC     lines=[s.strip() for s in section[1].splitlines() if s.strip()]
# MAGIC     found={}
# MAGIC     for i,line in enumerate(lines[:-1]):
# MAGIC         if re.fullmatch(r'\d{1,2}',line) and re.fullmatch(r'[A-Z]{2,5}-[A-Z0-9-]+',lines[i+1]):
# MAGIC             found[str(int(line))]=lines[i+1]
# MAGIC     return found
# MAGIC
# MAGIC def extract_pdf(pdf_bytes, source_file):
# MAGIC     doc=fitz.open(stream=pdf_bytes,filetype='pdf'); rows=[]
# MAGIC     for pidx,page in enumerate(doc):
# MAGIC         text=page.get_text('text')
# MAGIC         m=re.search(r'DRAWING ID:\s*(CAD-\d+)',text)
# MAGIC         drawing_id=m.group(1) if m else Path(source_file).stem.split('_')[0]
# MAGIC         lookup=bom_lookup(page)
# MAGIC         for word in page.get_text('words'):
# MAGIC             x0,y0,x1,y1,label,*_=word
# MAGIC             typ=classify(label,y0,page.rect.height)
# MAGIC             if not typ: continue
# MAGIC             part=lookup.get(str(int(label))) if typ=='component_callout' else None
# MAGIC             rows.append((drawing_id,source_file,pidx+1,label,typ,float(x0),float(y0),float(x1),float(y1),
# MAGIC                 float(page.rect.width),float(page.rect.height),part,'pdf_text_coordinates',
# MAGIC                 'MATCHED' if part else 'NEEDS_REVIEW'))
# MAGIC         # Whole-line dimension labels: PyMuPDF words split +/- and mm into tokens
# MAGIC         for block in page.get_text('dict')['blocks']:
# MAGIC             if 'lines' not in block:continue
# MAGIC             for line in block['lines']:
# MAGIC                 spans=line['spans']; s=' '.join(x['text'] for x in spans).strip()
# MAGIC                 if len(s)>90 or not re.search(r'\d',s):continue
# MAGIC                 typ=classify(s,line['bbox'][1],page.rect.height)
# MAGIC                 if typ not in ('dimension','tolerance_or_dimension','technical_specification'):continue
# MAGIC                 if any(r[3]==s and r[2]==pidx+1 for r in rows):continue
# MAGIC                 x0,y0,x1,y1=line['bbox']
# MAGIC                 rows.append((drawing_id,source_file,pidx+1,s,typ,float(x0),float(y0),float(x1),float(y1),
# MAGIC                     float(page.rect.width),float(page.rect.height),None,'pdf_text_coordinates','NEEDS_REVIEW'))
# MAGIC     return rows
# MAGIC
# MAGIC rows=[]
# MAGIC for f in dbutils.fs.ls(PDF_ROOT):
# MAGIC     if not f.name.lower().endswith('.pdf'):continue
# MAGIC     # Spark binaryFile is reliable on Unity Catalog Volumes
# MAGIC     rec=spark.read.format('binaryFile').load(f.path).select('content').first()
# MAGIC     rows.extend(extract_pdf(bytes(rec.content),f.path))
# MAGIC if not rows:raise RuntimeError('No labels found; verify PDFs and PDF_ROOT')
# MAGIC
# MAGIC # Same rule as 02b: one source file per drawing revision. A re-uploaded PDF of a known drawing
# MAGIC # revision (e.g. a UUID-named app upload of CAD-0007) must not duplicate labels.
# MAGIC # Drawing/revision per file comes from ai_extraction_raw; prefer the drawing_registry file, then the lowest path.
# MAGIC def val(x): return x.get('value') if isinstance(x,dict) and 'value' in x else x
# MAGIC registry={(r.drawing_id,r.revision):r.source_file for r in spark.table(f'{BASE}.drawing_registry').select('drawing_id','revision','source_file').collect()}
# MAGIC by_rev={}
# MAGIC for r in spark.sql(f'SELECT source_file, to_json(extracted) AS payload FROM {BASE}.ai_extraction_raw').collect():
# MAGIC     resp=json.loads(r.payload or '{}').get('response') or {}
# MAGIC     key=(str(val(resp.get('drawing_id')) or ''),str(val(resp.get('revision')) or ''))
# MAGIC     if all(key): by_rev.setdefault(key,[]).append(r.source_file)
# MAGIC dropped_files=set()
# MAGIC for key,files in by_rev.items():
# MAGIC     keep=sorted(files,key=lambda f:(Path(f).name!=registry.get(key),f))[0]
# MAGIC     dropped_files.update(f for f in files if f!=keep)
# MAGIC raw_count=len(rows)
# MAGIC rows=[r for r in rows if r[1] not in dropped_files]  # files without an extraction record are kept
# MAGIC print('DUPLICATE_FILES_SKIPPED=',sorted(Path(f).name for f in dropped_files),'| LABELS_DROPPED=',raw_count-len(rows))
# MAGIC
# MAGIC df=spark.createDataFrame(rows,schema)
# MAGIC df.write.mode('overwrite').option('overwriteSchema','true').saveAsTable(f'{BASE}.cad_annotations')
# MAGIC print('CAD_ANNOTATIONS_TOTAL=',df.count())
# MAGIC df.groupBy('label_type','review_status').count().orderBy('label_type').show(truncate=False)