# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "6"
# ///
# DBTITLE 1,Install PyMuPDF
# MAGIC %pip install -q "PyMuPDF>=1.24,<2"
# MAGIC # NEW 02d (OPTIONAL): multimodal extraction for labels that are rasterized / not selectable.
# MAGIC # Install PyMuPDF (databricks-sdk is preinstalled on the runtime); configure a VISION_ENDPOINT supporting image_url inputs.

# COMMAND ----------

# DBTITLE 1,Vision fallback extraction
import os, json, base64, fitz
from databricks.sdk import WorkspaceClient
from pyspark.sql import types as T
w=WorkspaceClient()
# Default to an image-capable Foundation Model endpoint; override via the VISION_ENDPOINT env var.
os.environ.setdefault('VISION_ENDPOINT','databricks-claude-sonnet-4-6')
endpoint=os.getenv('VISION_ENDPOINT','')
if not endpoint:
    raise ValueError('Set VISION_ENDPOINT to an image-capable serving endpoint before running')
root='/Volumes/gabi_bosch_sandbox_catalog/cad_intelligence/raw_drawings/incoming'
# Run against one PDF first; control costs and model context size.
pdfs=[x for x in dbutils.fs.ls(root) if x.name.lower().endswith('.pdf')]
if not pdfs:raise RuntimeError('No PDFs in incoming')
source=pdfs[0].path
pdf=bytes(spark.read.format('binaryFile').load(source).select('content').first().content)
page=fitz.open(stream=pdf,filetype='pdf')[0]
png=page.get_pixmap(matrix=fitz.Matrix(1.6,1.6),alpha=False).tobytes('png')
image_url='data:image/png;base64,'+base64.b64encode(png).decode('ascii')
request={
 'messages':[{'role':'system','content':'You extract visible labels from technical drawings. Never guess illegible labels. Return only JSON.'},
 {'role':'user','content':[
   {'type':'text','text':('Read the engineering drawing image. Return JSON object with key annotations, an array of objects with '
    'label_text, label_type (component_callout, dimension, tolerance, technical_specification), '
    'and bom_item if explicitly matched. Only transcribe what is visible. Do not invent bounding boxes.')},
   {'type':'image_url','image_url':{'url':image_url}}
 ]}], 'max_tokens':1500, 'temperature':0
}
# Serving endpoint API and accepted multimodal payload are endpoint-specific.
# This call uses the Databricks SDK API client to authenticate as the notebook identity.
result=w.api_client.do('POST',f'/serving-endpoints/{endpoint}/invocations',body=request)
print('VISION_ENDPOINT=',endpoint,'SOURCE=',source)
print(json.dumps(result,ensure_ascii=False,indent=2)[:10000])
# Review response, then normalize/merge it into cad_annotations only after validation.
# Do not silently overwrite the coordinate-grounded extraction from 02c.

# COMMAND ----------

# DBTITLE 1,Parse vision response and compare with 02c labels
import re
import pandas as pd

# 1) Parse the model response (strip optional ```json fences)
raw = result['choices'][0]['message']['content']
m = re.search(r'```(?:json)?\s*(.*?)\s*```', raw, re.S)
vision = json.loads(m.group(1) if m else raw)['annotations']
vdf = pd.DataFrame(vision)

def norm(s):
    s = (s or '').lower().replace('\u00b1', '+/-').replace('\u2300', '\u00f8')
    return re.sub(r'\s+', ' ', s).strip()

# Map vision callouts to part IDs via the BOM rows the model linked to the same bom_item
bom_parts = {r['bom_item']: r['label_text'].split('|')[0].strip()
             for r in vision if r.get('bom_item') and r['label_type'] != 'component_callout' and '|' in r['label_text']}
vdf['vision_part_id'] = vdf.apply(lambda r: bom_parts.get(r['bom_item']) if r['label_type'] == 'component_callout' else None, axis=1)
vdf['norm'] = vdf['label_text'].map(norm)

# 2) Load 02c coordinate-grounded labels for the same PDF/page (read-only)
c = (spark.table('gabi_bosch_sandbox_catalog.cad_intelligence.cad_annotations')
     .filter(f"source_file = '{source}' AND page_number = 1")
     .select('label_text', 'label_type', 'matched_part_id').toPandas())
c['norm'] = c['label_text'].map(norm)
print(f'Vision labels: {len(vdf)} | 02c labels for this page: {len(c)} | source: {source}')

# 3) Match each vision label: exact text, else 02c text contained in the vision text (e.g. Ø25 inside a BOM row)
def match(r):
    if r['label_type'] == 'component_callout':
        hits = c[(c.label_type == 'component_callout') & (c.norm.str.lstrip('0') == r['norm'].lstrip('0'))]
    else:
        hits = c[c.norm == r['norm']]
        if hits.empty:
            # Skip bare callout numbers (e.g. '01' would falsely match inside dates/IDs)
            hits = c[(c.label_type != 'component_callout') & c.norm.map(lambda t: len(t) >= 3 and t in r['norm'])]
            return pd.Series({'match': 'PARTIAL' if len(hits) else 'VISION_ONLY',
                              'c02_labels': '; '.join(hits.label_text.unique()), 'part_agrees': None})
    if hits.empty:
        return pd.Series({'match': 'VISION_ONLY', 'c02_labels': '', 'part_agrees': None})
    agree = None
    if r['label_type'] == 'component_callout':
        agree = bool(r['vision_part_id'] is not None and r['vision_part_id'] in set(hits.matched_part_id))
    return pd.Series({'match': 'EXACT', 'c02_labels': '; '.join(hits.label_text.unique()), 'part_agrees': agree})

cmp = pd.concat([vdf[['label_type', 'label_text', 'bom_item', 'vision_part_id']], vdf.apply(match, axis=1)], axis=1)
display(cmp)

# 4) 02c labels the vision model did not report
used = set(n for s in cmp.c02_labels for n in s.split('; ') if n)
# 02c word-level fragments (e.g. '+/-0.10' split from '240 +/-0.10 mm') are covered if contained in any vision label
c['covered'] = c.label_text.isin(used) | c.norm.map(lambda t: any(t in v for v in vdf.norm))
c_only = c[~c.covered][['label_type', 'label_text', 'matched_part_id']]
print(f'02c-only labels (not reported by vision): {len(c_only)}')
if len(c_only): display(c_only)
print(cmp['match'].value_counts().to_dict(), '| callout part agreement:',
      cmp.loc[cmp.label_type == 'component_callout', 'part_agrees'].value_counts().to_dict())