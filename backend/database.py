import sqlite3
import json
import logging
from datetime import datetime
from contextlib import contextmanager
from typing import Optional, List, Dict, Any
from config import settings
from models import HistoryEntry, Verdict

logger = logging.getLogger(__name__)


# ── CONNECTION ─────────────────────────────────────────────────────────────────

@contextmanager
def get_db():
    conn = sqlite3.connect(settings.DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── SCHEMA ─────────────────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS analysis_results (
    submission_id     TEXT PRIMARY KEY,
    applicant_id      TEXT,
    risk_score        REAL NOT NULL,
    verdict           TEXT NOT NULL,
    risk_level        TEXT NOT NULL,
    filenames         TEXT NOT NULL,
    total_flags       INTEGER DEFAULT 0,
    critical_flags    INTEGER DEFAULT 0,
    high_flags        INTEGER DEFAULT 0,
    layer_results     TEXT NOT NULL,
    score_data        TEXT NOT NULL,
    all_flags         TEXT NOT NULL DEFAULT '[]',
    report_text       TEXT NOT NULL DEFAULT '',
    processing_time_ms INTEGER DEFAULT 0,
    created_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS document_fingerprints (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    fingerprint       TEXT NOT NULL,
    filename          TEXT NOT NULL,
    file_hash         TEXT NOT NULL,
    applicant_id      TEXT,
    submission_id     TEXT,
    uploaded_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS blockchain_records (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    file_hash         TEXT NOT NULL UNIQUE,
    tx_hash           TEXT,
    notarized_at      TEXT NOT NULL,
    network           TEXT DEFAULT 'sepolia',
    verified          INTEGER DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_fingerprint ON document_fingerprints(fingerprint);
CREATE INDEX IF NOT EXISTS idx_file_hash ON document_fingerprints(file_hash);
CREATE INDEX IF NOT EXISTS idx_blockchain_hash ON blockchain_records(file_hash);
CREATE INDEX IF NOT EXISTS idx_results_created ON analysis_results(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_results_verdict ON analysis_results(verdict);
CREATE INDEX IF NOT EXISTS idx_results_applicant ON analysis_results(applicant_id);
"""


def init_db() -> None:
    with get_db() as conn:
        conn.executescript(SCHEMA)
    logger.info("Database initialized at %s", settings.DB_PATH)


# ── ANALYSIS RESULTS ───────────────────────────────────────────────────────────

def save_analysis_result(result: Dict[str, Any]) -> None:
    with get_db() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO analysis_results
            (submission_id, applicant_id, risk_score, verdict, risk_level,
             filenames, total_flags, critical_flags, high_flags,
             layer_results, score_data, all_flags, report_text,
             processing_time_ms, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            result["submission_id"],
            result.get("applicant_id"),
            result["risk_score"],
            result["verdict"],
            result["risk_level"],
            json.dumps(result.get("filenames", [])),
            result.get("total_flags", 0),
            result.get("critical_flags", 0),
            result.get("high_flags", 0),
            json.dumps(result.get("layer_results", []), default=str),
            json.dumps(result.get("score_data", {}), default=str),
            json.dumps(result.get("all_flags", []), default=str),
            result.get("report_text", ""),
            result.get("processing_time_ms", 0),
            datetime.utcnow().isoformat(),
        ))


def get_analysis_result(submission_id: str) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM analysis_results WHERE submission_id = ?",
            (submission_id,)
        ).fetchone()
        if not row:
            return None
        data = dict(row)
        data["layer_results"] = json.loads(data["layer_results"])
        data["score_data"] = json.loads(data["score_data"])
        data["all_flags"] = json.loads(data["all_flags"])
        data["filenames"] = json.loads(data["filenames"])
        return data


def get_history(page: int = 1, per_page: int = 20, verdict_filter: Optional[str] = None) -> Dict[str, Any]:
    offset = (page - 1) * per_page
    with get_db() as conn:
        where = "WHERE verdict = ?" if verdict_filter else ""
        params_count = (verdict_filter,) if verdict_filter else ()
        total = conn.execute(
            f"SELECT COUNT(*) FROM analysis_results {where}", params_count
        ).fetchone()[0]

        params = (*params_count, per_page, offset)
        rows = conn.execute(
            f"""SELECT submission_id, applicant_id, risk_score, verdict,
                       filenames, total_flags, created_at
                FROM analysis_results {where}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?""",
            params
        ).fetchall()

        entries = []
        for row in rows:
            entries.append({
                "submission_id": row["submission_id"],
                "applicant_id": row["applicant_id"],
                "risk_score": row["risk_score"],
                "verdict": row["verdict"],
                "filenames": json.loads(row["filenames"]),
                "total_flags": row["total_flags"],
                "created_at": row["created_at"],
            })

        return {"total": total, "entries": entries, "page": page, "per_page": per_page}


def get_stats() -> Dict[str, Any]:
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM analysis_results").fetchone()[0]
        by_verdict = conn.execute(
            "SELECT verdict, COUNT(*) as cnt FROM analysis_results GROUP BY verdict"
        ).fetchall()
        avg_score = conn.execute(
            "SELECT AVG(risk_score) FROM analysis_results"
        ).fetchone()[0] or 0.0
        return {
            "total": total,
            "by_verdict": {row["verdict"]: row["cnt"] for row in by_verdict},
            "avg_risk_score": round(avg_score, 1),
        }


# ── DOCUMENT FINGERPRINTS ──────────────────────────────────────────────────────

def save_fingerprint(fingerprint: str, filename: str, file_hash: str,
                     applicant_id: Optional[str] = None,
                     submission_id: Optional[str] = None) -> None:
    with get_db() as conn:
        conn.execute("""
            INSERT INTO document_fingerprints
            (fingerprint, filename, file_hash, applicant_id, submission_id, uploaded_at)
            VALUES (?,?,?,?,?,?)
        """, (fingerprint, filename, file_hash, applicant_id, submission_id,
              datetime.utcnow().isoformat()))


def get_fingerprint_history(fingerprint: str) -> List[Dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM document_fingerprints WHERE fingerprint = ? ORDER BY uploaded_at DESC",
            (fingerprint,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_hash_history(file_hash: str) -> List[Dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM document_fingerprints WHERE file_hash = ? ORDER BY uploaded_at DESC",
            (file_hash,)
        ).fetchall()
        return [dict(r) for r in rows]


# ── BLOCKCHAIN RECORDS ─────────────────────────────────────────────────────────

def save_blockchain_record(file_hash: str, tx_hash: Optional[str] = None,
                           network: str = "sepolia") -> None:
    with get_db() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO blockchain_records (file_hash, tx_hash, notarized_at, network)
            VALUES (?,?,?,?)
        """, (file_hash, tx_hash, datetime.utcnow().isoformat(), network))


def get_blockchain_record(file_hash: str) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM blockchain_records WHERE file_hash = ?",
            (file_hash,)
        ).fetchone()
        return dict(row) if row else None
