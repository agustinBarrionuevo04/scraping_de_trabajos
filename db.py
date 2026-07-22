from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from models import Job

logger = logging.getLogger(__name__)


def _ensure_columns(conn: sqlite3.Connection) -> None:
    cur = conn.execute("PRAGMA table_info(jobs)")
    columns = {row[1] for row in cur.fetchall()}
    if "match_score" not in columns:
        conn.execute("ALTER TABLE jobs ADD COLUMN match_score REAL")
        logger.info("Added column match_score to jobs table")
    if "scored_at" not in columns:
        conn.execute("ALTER TABLE jobs ADD COLUMN scored_at TEXT")
        logger.info("Added column scored_at to jobs table")
    conn.commit()


def init_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            location TEXT NOT NULL,
            description TEXT NOT NULL,
            url TEXT NOT NULL,
            source TEXT NOT NULL,
            posted_date TEXT,
            salary_min REAL,
            salary_max REAL,
            scraped_at TEXT NOT NULL,
            match_score REAL,
            scored_at TEXT
        )
    """)
    conn.commit()
    _ensure_columns(conn)
    logger.info("Database initialized at %s", db_path)
    return conn


def exists(conn: sqlite3.Connection, job_id: str) -> bool:
    cur = conn.execute("SELECT 1 FROM jobs WHERE id = ?", (job_id,))
    return cur.fetchone() is not None


def upsert_job(conn: sqlite3.Connection, job: Job) -> str:
    action: str
    if exists(conn, job.id):
        conn.execute(
            "UPDATE jobs SET scraped_at = ? WHERE id = ?",
            (job.scraped_at, job.id),
        )
        action = "updated"
    else:
        conn.execute(
            """
            INSERT INTO jobs
                (id, title, company, location, description, url, source,
                 posted_date, salary_min, salary_max, scraped_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job.id,
                job.title,
                job.company,
                job.location,
                job.description,
                job.url,
                job.source,
                job.posted_date,
                job.salary_min,
                job.salary_max,
                job.scraped_at,
            ),
        )
        action = "inserted"
    conn.commit()
    return action


def job_exists(conn: sqlite3.Connection, job: Job) -> bool:
    return exists(conn, job.id)


def count_jobs(conn: sqlite3.Connection) -> int:
    cur = conn.execute("SELECT COUNT(*) FROM jobs")
    return cur.fetchone()[0]


def get_unscored_jobs(conn: sqlite3.Connection) -> list[dict]:
    cur = conn.execute(
        "SELECT id, description FROM jobs WHERE match_score IS NULL"
    )
    return [{"id": row[0], "description": row[1]} for row in cur.fetchall()]


def get_all_jobs(conn: sqlite3.Connection) -> list[dict]:
    cur = conn.execute("SELECT id, description FROM jobs")
    return [{"id": row[0], "description": row[1]} for row in cur.fetchall()]


def update_score(conn: sqlite3.Connection, job_id: str, score: float) -> None:
    conn.execute(
        "UPDATE jobs SET match_score = ?, scored_at = ? WHERE id = ?",
        (score, datetime.now(timezone.utc).isoformat(), job_id),
    )
    conn.commit()


def get_pending_count(conn: sqlite3.Connection) -> int:
    cur = conn.execute("SELECT COUNT(*) FROM jobs WHERE match_score IS NULL")
    return cur.fetchone()[0]


def get_top_scored(conn: sqlite3.Connection, threshold: float, limit: int = 10) -> list[dict]:
    cur = conn.execute(
        """
        SELECT title, company, match_score, source
        FROM jobs
        WHERE match_score IS NOT NULL AND match_score >= ?
        ORDER BY match_score DESC
        LIMIT ?
        """,
        (threshold, limit),
    )
    return [
        {"title": row[0], "company": row[1], "score": row[2], "source": row[3]}
        for row in cur.fetchall()
    ]


def count_above_threshold(conn: sqlite3.Connection, threshold: float) -> int:
    cur = conn.execute(
        "SELECT COUNT(*) FROM jobs WHERE match_score IS NOT NULL AND match_score >= ?",
        (threshold,),
    )
    return cur.fetchone()[0]
