import json
from pathlib import Path
import sqlite3
from contextlib import contextmanager
from .files import now


class Database:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS records (kind TEXT NOT NULL, id TEXT NOT NULL, revision INTEGER NOT NULL, body TEXT NOT NULL, archived INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(kind,id))')
            db.execute('CREATE TABLE IF NOT EXISTS revisions (kind TEXT NOT NULL, id TEXT NOT NULL, revision INTEGER NOT NULL, body TEXT NOT NULL, created TEXT NOT NULL, PRIMARY KEY(kind,id,revision))')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.execute('PRAGMA journal_mode=WAL')
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def list(self, kind, archived=False):
        with self.connect() as db:
            rows=db.execute('SELECT body,revision FROM records WHERE kind=? AND archived=? ORDER BY rowid DESC',(kind,int(archived))).fetchall()
        return [{**json.loads(r['body']),'revision':r['revision']} for r in rows]

    def get(self, kind, identifier):
        with self.connect() as db:
            row=db.execute('SELECT body,revision,archived FROM records WHERE kind=? AND id=?',(kind,identifier)).fetchone()
        if not row:
            raise ValueError('记录不存在。')
        return {**json.loads(row['body']),'revision':row['revision'],'archived':bool(row['archived'])}

    def save(self, kind, body, expected=None):
        identifier=body['id']
        body={k:v for k,v in body.items() if k not in {'revision','archived'}}
        encoded=json.dumps(body,ensure_ascii=False)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT revision FROM records WHERE kind=? AND id=?',(kind,identifier)).fetchone()
            if row and (expected is None or expected != row['revision']):
                raise ValueError('记录已经更新，请刷新后再操作，避免覆盖另一页面的修改。')
            if not row and expected not in (None,0):
                raise ValueError('新记录版本无效。')
            revision=row['revision']+1 if row else 1
            db.execute('INSERT INTO records(kind,id,revision,body) VALUES(?,?,?,?) ON CONFLICT(kind,id) DO UPDATE SET revision=excluded.revision,body=excluded.body',(kind,identifier,revision,encoded))
            db.execute('INSERT INTO revisions VALUES(?,?,?,?,?)',(kind,identifier,revision,encoded,now()))
        return self.get(kind,identifier)

    def archive(self, kind, identifier, archived, expected):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT body FROM records WHERE kind=? AND id=? AND revision=?',(kind,identifier,expected)).fetchone()
            if row is None:raise ValueError('记录版本已变化，请刷新。')
            body=json.loads(row['body']);body.setdefault('archiveEvents',[]).append({'archived':archived,'at':now()})
            encoded=json.dumps(body,ensure_ascii=False)
            result=db.execute('UPDATE records SET archived=?,revision=revision+1,body=? WHERE kind=? AND id=? AND revision=?',(int(archived),encoded,kind,identifier,expected))
            if result.rowcount != 1:
                raise ValueError('记录版本已变化，请刷新。')
            db.execute('INSERT INTO revisions VALUES(?,?,?,?,?)',(kind,identifier,expected+1,encoded,now()))
        return self.get(kind,identifier)
