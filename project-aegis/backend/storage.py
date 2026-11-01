"""SQLite persistence for Aegis operational records."""
from __future__ import annotations
import json, sqlite3
from contextlib import contextmanager
from pathlib import Path
from collections.abc import Iterator
from typing import Any
DB_PATH=Path(__file__).resolve().parent.parent/'data'/'aegis.db'

@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    DB_PATH.parent.mkdir(parents=True,exist_ok=True)
    connection=sqlite3.connect(DB_PATH,timeout=10)
    connection.row_factory=sqlite3.Row
    try:
        connection.execute('PRAGMA busy_timeout=5000')
        connection.execute('''CREATE TABLE IF NOT EXISTS records (id TEXT PRIMARY KEY, kind TEXT NOT NULL, payload TEXT NOT NULL, updated_at TEXT NOT NULL)''')
        connection.commit()
        yield connection
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

def save(kind:str,item:dict[str,Any]):
    with connect() as c: c.execute('INSERT OR REPLACE INTO records(id,kind,payload,updated_at) VALUES(?,?,?,datetime("now"))',(item['id'],kind,json.dumps(item,ensure_ascii=False))); c.commit()

def load(kind:str):
    with connect() as c: return [json.loads(r['payload']) for r in c.execute('SELECT payload FROM records WHERE kind=? ORDER BY updated_at,rowid',(kind,))]

def delete_all(kind:str):
    with connect() as c: c.execute('DELETE FROM records WHERE kind=?',(kind,)); c.commit()

def delete_record(kind:str,record_id:str):
    with connect() as c:
        cursor=c.execute('DELETE FROM records WHERE kind=? AND id=?',(kind,record_id)); c.commit()
        return cursor.rowcount>0

def audit(action:str,actor:str,record_id:str|None=None,details:dict[str,Any]|None=None):
    from datetime import datetime,timezone
    item={'id':f'AUD-{__import__("uuid").uuid4().hex[:12].upper()}','action':action,'actor':actor,'record_id':record_id,'details':details or {},'timestamp':datetime.now(timezone.utc).isoformat()}
    save('audit',item)
    return item
