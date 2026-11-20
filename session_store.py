"""Local, transactional session persistence; never store audio or service credentials."""
import json
from pathlib import Path
import sqlite3
import os
from contextlib import closing

DEFAULT_PATH = Path(os.getenv('DATA_DIR') or Path(__file__).resolve().parent / '.local').expanduser() / 'sessions.sqlite3'


class SessionConflict(ValueError):
    """A concurrent writer has already saved a newer debate revision."""


class SessionStore:
    def __init__(self, path=DEFAULT_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, state TEXT NOT NULL, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)')
            columns = {row[1] for row in db.execute('PRAGMA table_info(sessions)')}
            if 'owner_id' not in columns:
                db.execute('ALTER TABLE sessions ADD COLUMN owner_id TEXT')
            db.execute('CREATE INDEX IF NOT EXISTS session_owner ON sessions(owner_id)')

    def save(self, state, expected_revision=None):
        payload = json.dumps(state, allow_nan=False)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            if expected_revision is not None:
                saved=db.execute('SELECT state FROM sessions WHERE id=?',(state['id'],)).fetchone()
                if saved is None or json.loads(saved[0]).get('revision') != expected_revision:
                    raise SessionConflict('This debate changed before the update was saved.')
            db.execute('INSERT INTO sessions(id,state,owner_id) VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET state=excluded.state, owner_id=COALESCE(sessions.owner_id,excluded.owner_id), updated_at=CURRENT_TIMESTAMP', (state['id'],payload,state.get('owner_id')))

    def load(self, session_id):
        with closing(sqlite3.connect(self.path)) as db:
            row = db.execute('SELECT state,owner_id FROM sessions WHERE id=?',(session_id,)).fetchone()
        if row:
            state=json.loads(row[0])
            if row[1] is not None:
                state['owner_id']=row[1]
            return state
        return None

    def list(self, owner_id=None):
        with closing(sqlite3.connect(self.path)) as db:
            query='SELECT state,owner_id FROM sessions'
            args=()
            if owner_id is not None:
                query+=' WHERE owner_id=?'
                args=(owner_id,)
            states=[]
            for row in db.execute(query+' ORDER BY updated_at DESC',args):
                state=json.loads(row[0])
                if row[1] is not None:
                    state['owner_id']=row[1]
                states.append(state)
            return states


def feedback_records(state):
    records = []
    for alert in state['alerts']:
        if not alert.get('feedback'):
            continue
        turn = next(t for t in state['turns'] if t['number'] == alert['turn'])
        records.append({"session_id": state['id'], "alert_id": alert['id'], "topic": state['topic'],
                        "kind": alert['kind'], "speaker": turn['speaker'], "turn": turn['number'], "text": turn['text'],
                        "context": [{"number": t['number'], "speaker": t['speaker'], "text": t['text']}
                                    for t in state['turns'] if turn['number']-4 <= t['number'] < turn['number']],
                        "attack_probability": turn['attack_probability'], "topic_result": turn['topic'],
                        "detectors": state.get('detectors'), "feedback": alert['feedback'],
                        "example_session": bool(state.get('example')), "requires_dataset_review": True})
    return records
