import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DATABASE_PATH = Path(__file__).parent / 'data' / 'investment_journal.db'

def connection():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DATABASE_PATH)
    db.row_factory = sqlite3.Row
    return db

def initialize_database():
    with connection() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL,
            ticker TEXT NOT NULL, current_price REAL, entry_price REAL NOT NULL,
            stop_loss REAL NOT NULL, target_price REAL NOT NULL, risk_reward REAL NOT NULL,
            decision TEXT NOT NULL, notes TEXT)''')

def save_decision(**values: Any) -> int:
    payload = {**values, 'created_at': datetime.now(timezone.utc).replace(microsecond=0).isoformat()}
    cols = ', '.join(payload); marks = ', '.join(f':{k}' for k in payload)
    with connection() as db:
        cur = db.execute(f'INSERT INTO decisions ({cols}) VALUES ({marks})', payload)
        return int(cur.lastrowid)

def get_decisions(limit=250):
    with connection() as db:
        rows = db.execute('SELECT * FROM decisions ORDER BY id DESC LIMIT ?', (limit,)).fetchall()
    return [dict(r) for r in rows]
