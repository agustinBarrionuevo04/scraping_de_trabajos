from __future__ import annotations

import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

from db import (
    count_above_threshold,
    get_all_jobs,
    get_pending_count,
    get_top_scored,
    get_unscored_jobs,
    init_db,
    update_score,
    upsert_job,
)
from models import Job


def make_job(
    title: str = "Data Scientist",
    company: str = "Acme Corp",
    source: str = "linkedin",
    description: str = "Looking for a data scientist with Python and ML experience",
) -> Job:
    return Job(
        title=title,
        company=company,
        location="Remote",
        description=description,
        url="https://example.com/job/1",
        source=source,
    )


class TestScoring:
    @pytest.fixture
    def db_conn(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        conn = init_db(db_path)
        yield conn
        conn.close()
        os.unlink(db_path)

    def test_columns_added(self, db_conn):
        cur = db_conn.execute("PRAGMA table_info(jobs)")
        columns = {row[1] for row in cur.fetchall()}
        assert "match_score" in columns
        assert "scored_at" in columns

    def test_get_unscored_jobs_empty(self, db_conn):
        jobs = get_unscored_jobs(db_conn)
        assert jobs == []

    def test_get_unscored_jobs_after_insert(self, db_conn):
        job = make_job()
        upsert_job(db_conn, job)
        unscored = get_unscored_jobs(db_conn)
        assert len(unscored) == 1
        assert unscored[0]["id"] == job.id
        assert unscored[0]["description"] == job.description

    def test_get_all_jobs(self, db_conn):
        upsert_job(db_conn, make_job(title="Job A"))
        upsert_job(db_conn, make_job(title="Job B", company="Other Co"))
        all_jobs = get_all_jobs(db_conn)
        assert len(all_jobs) == 2

    def test_update_score(self, db_conn):
        job = make_job()
        upsert_job(db_conn, job)
        update_score(db_conn, job.id, 0.85)

        cur = db_conn.execute(
            "SELECT match_score, scored_at FROM jobs WHERE id = ?", (job.id,)
        )
        row = cur.fetchone()
        assert row is not None
        assert row[0] == 0.85
        assert row[1] is not None

    def test_score_clears_unscored_count(self, db_conn):
        job = make_job()
        upsert_job(db_conn, job)
        assert get_pending_count(db_conn) == 1
        update_score(db_conn, job.id, 0.75)
        assert get_pending_count(db_conn) == 0

    def test_count_above_threshold(self, db_conn):
        jobs = [
            make_job(title="A", source="linkedin"),
            make_job(title="B", source="indeed", company="Foo"),
            make_job(title="C", source="adzuna", company="Bar"),
        ]
        for j in jobs:
            upsert_job(db_conn, j)

        update_score(db_conn, jobs[0].id, 0.8)
        update_score(db_conn, jobs[1].id, 0.3)
        update_score(db_conn, jobs[2].id, 0.5)

        assert count_above_threshold(db_conn, 0.5) == 2
        assert count_above_threshold(db_conn, 0.7) == 1
        assert count_above_threshold(db_conn, 0.9) == 0

    def test_get_top_scored(self, db_conn):
        jobs = [
            make_job(title="A", company="BestCo", source="linkedin"),
            make_job(title="B", company="MidCo", source="indeed"),
            make_job(title="C", company="LowCo", source="glassdoor"),
        ]
        for j in jobs:
            upsert_job(db_conn, j)

        update_score(db_conn, jobs[0].id, 0.9)
        update_score(db_conn, jobs[1].id, 0.6)
        update_score(db_conn, jobs[2].id, 0.2)

        top = get_top_scored(db_conn, threshold=0.5, limit=10)
        assert len(top) == 2
        assert top[0]["title"] == "A"
        assert top[0]["score"] == 0.9
        assert top[1]["title"] == "B"

    def test_rescore_all_flag(self, db_conn):
        job = make_job()
        upsert_job(db_conn, job)
        update_score(db_conn, job.id, 0.7)

        assert get_pending_count(db_conn) == 0
        assert len(get_unscored_jobs(db_conn)) == 0
        assert len(get_all_jobs(db_conn)) == 1

        update_score(db_conn, job.id, 0.95)
        cur = db_conn.execute(
            "SELECT match_score FROM jobs WHERE id = ?", (job.id,)
        )
        assert cur.fetchone()[0] == 0.95

    def test_score_in_range(self, db_conn):
        job = make_job()
        upsert_job(db_conn, job)
        update_score(db_conn, job.id, 0.73)

        cur = db_conn.execute(
            "SELECT match_score FROM jobs WHERE id = ?", (job.id,)
        )
        score = cur.fetchone()[0]
        assert 0.0 <= score <= 1.0


class TestProfileLoading:
    def test_profile_not_found(self):
        from scoring import load_profile

        with pytest.raises(FileNotFoundError):
            load_profile("/nonexistent/path/profile.txt")

    def test_profile_loading(self):
        from scoring import load_profile

        content = "Soy un Data Scientist con experiencia en Python y ML."
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write(content)
            path = f.name

        try:
            result = load_profile(path)
            assert result == content
        finally:
            os.unlink(path)

    def test_empty_profile(self):
        from scoring import load_profile

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write("   \n  ")
            path = f.name

        try:
            with pytest.raises(ValueError, match="vacío"):
                load_profile(path)
        finally:
            os.unlink(path)
