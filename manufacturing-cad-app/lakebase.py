"""Lakebase Autoscaling: OAuth token generated for every new Postgres connection."""
import os
import psycopg
from databricks.sdk import WorkspaceClient

# The app service principal cannot create objects in the existing 'public' schema,
# so it creates and owns its own schema.
PG_SCHEMA='cad_app'

def connect():
    required=['PGHOST','PGDATABASE','ENDPOINT_NAME']
    missing=[x for x in required if not os.getenv(x)]
    if missing: raise RuntimeError('Missing Lakebase configuration: '+','.join(missing))
    w=WorkspaceClient()
    credential=w.postgres.generate_database_credential(endpoint=os.environ['ENDPOINT_NAME'])
    # The Postgres user must be the identity the OAuth token was issued to (the app service principal when deployed)
    user=w.current_user.me().user_name
    return psycopg.connect(host=os.environ['PGHOST'], dbname=os.environ['PGDATABASE'],
        user=user,port=int(os.getenv('PGPORT','5432')),
        password=credential.token,sslmode='require',
        options=f'-c search_path={PG_SCHEMA}')

def init():
    with connect() as c:
        c.execute(f'CREATE SCHEMA IF NOT EXISTS {PG_SCHEMA}')
        c.execute('''CREATE TABLE IF NOT EXISTS document_review (
          document_id TEXT PRIMARY KEY, file_name TEXT NOT NULL, status TEXT NOT NULL,
          notes TEXT DEFAULT '', updated_at TIMESTAMPTZ DEFAULT now())''')

def upsert_review(document_id,file_name,status,notes=''):
    with connect() as c:
        c.execute('''INSERT INTO document_review(document_id,file_name,status,notes)
          VALUES(%s,%s,%s,%s) ON CONFLICT(document_id) DO UPDATE SET
          status=excluded.status,notes=excluded.notes,updated_at=now()''',
          (document_id,file_name,status,notes))

def reviews():
    with connect() as c:
        return c.execute('SELECT document_id,file_name,status,notes,updated_at FROM document_review ORDER BY updated_at DESC LIMIT 100').fetchall()
