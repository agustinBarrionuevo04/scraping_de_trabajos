from __future__ import annotations

import os
import sqlite3
import tempfile

import pytest

from db import init_db, job_exists, upsert_job
from models import Job


def make_job(title: str = "Data Scientist", company: str = "Acme Corp", source: str = "linkedin") -> Job:
    return Job(
        title=title,
        company=company,
        location="Remote",
        description="A great job",
        url="https://example.com/job/1",
        source=source,
    )


def test_id_is_deterministic() -> None:
    j1 = make_job()
    j2 = make_job()
    assert j1.id == j2.id


def test_id_differs_on_title() -> None:
    j1 = make_job(title="Data Scientist")
    j2 = make_job(title="ML Engineer")
    assert j1.id != j2.id


def test_id_differs_on_company() -> None:
    j1 = make_job(company="Acme Corp")
    j2 = make_job(company="Foo Inc")
    assert j1.id != j2.id


def test_id_differs_on_source() -> None:
    j1 = make_job(source="linkedin")
    j2 = make_job(source="indeed")
    assert j1.id != j2.id


def test_upsert_inserts_new_job() -> None:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        conn = init_db(db_path)
        job = make_job()
        assert not job_exists(conn, job)

        action = upsert_job(conn, job)
        assert action == "inserted"
        assert job_exists(conn, job)

        conn.close()
    finally:
        os.unlink(db_path)


def test_upsert_updates_existing_job_scraped_at() -> None:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        conn = init_db(db_path)
        job = make_job()

        upsert_job(conn, job)

        job.scraped_at = "2024-01-01T00:00:00+00:00"
        action = upsert_job(conn, job)
        assert action == "updated"

        cur = conn.execute("SELECT scraped_at FROM jobs WHERE id = ?", (job.id,))
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "2024-01-01T00:00:00+00:00"

        conn.close()
    finally:
        os.unlink(db_path)


def test_cross_source_dedupe() -> None:
    job_linkedin = make_job(source="linkedin")
    job_indeed = make_job(source="indeed")
    job_adzuna = make_job(source="adzuna")

    assert job_linkedin.id != job_indeed.id
    assert job_indeed.id != job_adzuna.id
    assert job_linkedin.id != job_adzuna.id


def test_job_exists_returns_false_for_nonexistent() -> None:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        conn = init_db(db_path)
        job = make_job()
        assert not job_exists(conn, job)
        conn.close()
    finally:
        os.unlink(db_path)
