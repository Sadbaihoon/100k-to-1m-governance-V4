from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DATABASE_PATH = Path(__file__).parent / 'data' / 'investment_journal.db'
GOVERNANCE_VERSION = 'V4.1'

# V4.1 is an additive storage migration. Existing rows are preserved.
MIGRATION_COLUMNS: dict[str, str] = {
    'snapshot_json': 'TEXT',
    'process_status': 'TEXT',
    'thesis_status': 'TEXT',
    'short_term_regime': 'TEXT',
    'long_term_regime': 'TEXT',
    'research_score': 'REAL',
    'evidence_coverage': 'REAL',
    'risk_score': 'REAL',
    'early_warning_status': 'TEXT',
    'rr_threshold': 'REAL',
    'rr_pass': 'INTEGER',
    'decision_reason': 'TEXT',
    'governance_version': 'TEXT',
    'data_as_of': 'TEXT',
}


def connection() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DATABASE_PATH)
    db.row_factory = sqlite3.Row
    return db


def _table_columns(db: sqlite3.Connection) -> set[str]:
    rows = db.execute('PRAGMA table_info(decisions)').fetchall()
    return {str(row['name']) for row in rows}


def _ensure_decisions_table(db: sqlite3.Connection) -> None:
    db.execute('''CREATE TABLE IF NOT EXISTS decisions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        ticker TEXT NOT NULL,
        current_price REAL,
        entry_price REAL NOT NULL,
        stop_loss REAL NOT NULL,
        target_price REAL NOT NULL,
        risk_reward REAL NOT NULL,
        decision TEXT NOT NULL,
        notes TEXT
    )''')


def _migrate_schema(db: sqlite3.Connection) -> None:
    existing = _table_columns(db)
    for name, sql_type in MIGRATION_COLUMNS.items():
        if name not in existing:
            db.execute(f'ALTER TABLE decisions ADD COLUMN {name} {sql_type}')


def _json_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _snapshot_from_notes(notes: Any) -> tuple[dict[str, Any], dict[str, Any], str]:
    """Extract the V4 audit payload used by the current app.

    Current V4 writes notes as:
      {"snapshot": snap, "process_checks": {...}, "notes": "..."}

    The complete payload is preserved as the immutable snapshot_json.
    """
    payload = _json_dict(notes)
    snapshot = payload.get('snapshot')
    if not isinstance(snapshot, dict):
        snapshot = {}
    return payload, snapshot, str(payload.get('notes', '') or '')


def _first(d: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = d.get(key)
        if value is not None:
            return value
    return None


def _derived_fields(payload: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    research = snapshot.get('research_evidence') or {}
    risk = snapshot.get('risk') or {}
    early = snapshot.get('early_warning') or {}
    regime = snapshot.get('regime') or {}
    decision = snapshot.get('decision') or {}
    rr = snapshot.get('risk_reward') or {}
    process_checks = payload.get('process_checks') or {}

    # Current V4 snapshot keys are preferred; aliases keep the migration resilient.
    process_status = _first(snapshot, 'process_status')
    if process_status is None:
        process_status = 'READY FOR HUMAN REVIEW' if process_checks and all(bool(v) for v in process_checks.values()) else 'PROCESS INCOMPLETE'

    thesis_status = _first(snapshot, 'thesis_status')
    if thesis_status is None:
        thesis_status = _first(snapshot.get('thesis') or {}, 'status')

    return {
        'process_status': process_status,
        'thesis_status': thesis_status,
        'short_term_regime': _first(regime, 'short_term'),
        'long_term_regime': _first(regime, 'long_term'),
        'research_score': _first(research, 'score'),
        'evidence_coverage': _first(research, 'coverage'),
        'risk_score': _first(risk, 'score'),
        'early_warning_status': _first(early, 'status'),
        'rr_threshold': _first(rr, 'threshold') or 2.0,
        'rr_pass': int(bool(_first(rr, 'pass')) if _first(rr, 'pass') is not None else (_first(rr, 'rr_ratio') or 0) >= 2.0),
        'decision_reason': _first(decision, 'reason'),
        'governance_version': GOVERNANCE_VERSION,
        'data_as_of': _first(snapshot, 'data_as_of') or _first(payload, 'data_as_of'),
    }


def _backfill_legacy_rows(db: sqlite3.Connection) -> None:
    """Populate V4.1 columns for existing V4 rows without changing their source notes."""
    rows = db.execute(
        '''SELECT id, notes, governance_version FROM decisions
           WHERE snapshot_json IS NULL OR snapshot_json = ''
              OR governance_version IS NULL'''
    ).fetchall()

    for row in rows:
        payload, snapshot, _ = _snapshot_from_notes(row['notes'])
        if not payload and not snapshot:
            # Preserve non-JSON legacy notes. There is no safe way to invent a snapshot.
            db.execute(
                '''UPDATE decisions
                   SET governance_version = COALESCE(governance_version, ?)
                   WHERE id = ?''',
                (GOVERNANCE_VERSION, row['id']),
            )
            continue

        derived = _derived_fields(payload, snapshot)
        # Canonical immutable representation: keep the exact parsed audit payload,
        # serialized deterministically so historical records do not depend on live data.
        snapshot_json = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
        db.execute(
            '''UPDATE decisions SET
                snapshot_json = ?,
                process_status = ?,
                thesis_status = ?,
                short_term_regime = ?,
                long_term_regime = ?,
                research_score = ?,
                evidence_coverage = ?,
                risk_score = ?,
                early_warning_status = ?,
                rr_threshold = ?,
                rr_pass = ?,
                decision_reason = ?,
                governance_version = ?,
                data_as_of = ?
               WHERE id = ?''',
            (
                snapshot_json,
                derived['process_status'],
                derived['thesis_status'],
                derived['short_term_regime'],
                derived['long_term_regime'],
                derived['research_score'],
                derived['evidence_coverage'],
                derived['risk_score'],
                derived['early_warning_status'],
                derived['rr_threshold'],
                derived['rr_pass'],
                derived['decision_reason'],
                derived['governance_version'],
                derived['data_as_of'],
                row['id'],
            ),
        )


def initialize_database() -> None:
    with connection() as db:
        _ensure_decisions_table(db)
        _migrate_schema(db)
        _backfill_legacy_rows(db)


def save_decision(**values: Any) -> int:
    """Save a decision and freeze its governance snapshot.

    Backward compatible with the current V4 app: when `notes` contains the
    current V4 audit JSON, V4.1 relational fields are derived automatically.
    Optional explicit V4.1 fields may also be supplied by future app versions.
    """
    initialize_database()

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    payload = dict(values)
    payload.setdefault('created_at', now)

    audit_payload, snapshot, _ = _snapshot_from_notes(payload.get('notes'))
    if audit_payload:
        derived = _derived_fields(audit_payload, snapshot)
        payload.setdefault('snapshot_json', json.dumps(audit_payload, ensure_ascii=False, sort_keys=True, default=str))
        for key, value in derived.items():
            payload.setdefault(key, value)
    else:
        payload.setdefault('governance_version', GOVERNANCE_VERSION)

    # Explicitly supplied fields always win over derived values.
    cols = ', '.join(payload)
    marks = ', '.join(f':{k}' for k in payload)
    with connection() as db:
        cur = db.execute(f'INSERT INTO decisions ({cols}) VALUES ({marks})', payload)
        return int(cur.lastrowid)


def get_decisions(limit: int = 250) -> list[dict[str, Any]]:
    initialize_database()
    with connection() as db:
        rows = db.execute(
            'SELECT * FROM decisions ORDER BY id DESC LIMIT ?',
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_decision(decision_id: int) -> dict[str, Any] | None:
    """Return one frozen Decision Log record by ID."""
    initialize_database()
    with connection() as db:
        row = db.execute(
            'SELECT * FROM decisions WHERE id = ?',
            (decision_id,),
        ).fetchone()
    return dict(row) if row else None
