#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import yaml

from db import count_jobs, init_db, upsert_job
from models import Job
from role_filter import filter_by_role
from sources.adzuna_source import scrape as scrape_adzuna
from sources.jobspy_source import scrape as scrape_jobspy

logger = logging.getLogger("scraper")


def setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    handler_stdout = logging.StreamHandler(sys.stdout)
    handler_file = logging.FileHandler("scraper.log")
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    handler_stdout.setFormatter(formatter)
    handler_file.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(handler_stdout)
    root.addHandler(handler_file)


def load_config(config_path: str) -> dict:
    with open(config_path, "r") as f:
        cfg = yaml.safe_load(f)
    if not cfg:
        raise ValueError(f"Config file {config_path} is empty or invalid")
    return cfg


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scrape job listings for Data Science / ML roles"
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to YAML config file (default: config.yaml)",
    )
    parser.add_argument(
        "--db",
        default="jobs.db",
        help="Path to SQLite database (default: jobs.db)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not write to DB, only report how many new jobs would be found",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "--score",
        action="store_true",
        help="Run semantic scoring on jobs using profile.txt",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.5,
        help="Minimum match score to show in summary (default: 0.5)",
    )
    parser.add_argument(
        "--rescore-all",
        action="store_true",
        help="Rescore all jobs (even already scored ones)",
    )
    return parser.parse_args()


def process_jobs(
    jobs: list[Job],
    db_path: str,
    dry_run: bool,
) -> tuple[int, int]:
    if dry_run:
        conn = init_db(db_path)
        new_count = 0
        for job in jobs:
            from db import job_exists
            if not job_exists(conn, job):
                new_count += 1
        conn.close()
        return new_count, 0

    conn = init_db(db_path)
    inserted = 0
    updated = 0
    for job in jobs:
        action = upsert_job(conn, job)
        if action == "inserted":
            inserted += 1
        else:
            updated += 1
    total = count_jobs(conn)
    conn.close()
    logger.info(
        "DB: inserted=%d updated=%d total_in_db=%d",
        inserted,
        updated,
        total,
    )
    return inserted, updated


def main() -> None:
    args = parse_args()
    setup_logging(args.verbose)

    config_path = Path(args.config)
    if not config_path.exists():
        logger.error("Config file not found: %s", config_path)
        sys.exit(1)

    config = load_config(str(config_path))

    search_terms: list[str] = config.get("search_terms", [])
    locations: list[str] = config.get("locations", [])
    results_per_search: int = config.get("results_per_search", 50)
    delay_seconds: float = config.get("delay_seconds", 4)

    if not search_terms:
        logger.error("No search_terms defined in config")
        sys.exit(1)
    if not locations:
        logger.error("No locations defined in config")
        sys.exit(1)

    logger.info("Starting scraper (dry_run=%s)", args.dry_run)
    logger.info("Search terms: %s", search_terms)
    logger.info("Locations: %s", locations)

    all_jobs: list[Job] = []

    try:
        logger.info("--- JobSpy source ---")
        jobspy_jobs = scrape_jobspy(search_terms, locations, results_per_search, delay_seconds)
        all_jobs.extend(jobspy_jobs)
        logger.info("JobSpy total: %d jobs", len(jobspy_jobs))
    except Exception:
        logger.exception("JobSpy source failed entirely")

    try:
        logger.info("--- Adzuna source ---")
        adzuna_jobs = scrape_adzuna(search_terms, locations, results_per_search, delay_seconds)
        all_jobs.extend(adzuna_jobs)
        logger.info("Adzuna total: %d jobs", len(adzuna_jobs))
    except Exception:
        logger.exception("Adzuna source failed entirely")

    roles: list[str] = config.get("roles", [])
    if roles:
        before = len(all_jobs)
        all_jobs = [job for job in all_jobs if filter_by_role(job.title, roles)]
        filtered = before - len(all_jobs)
        if filtered:
            logger.info("Role filter: dropped %d jobs, kept %d (roles=%s)", filtered, len(all_jobs), roles)

    unique_ids = len({job.id for job in all_jobs})
    logger.info("Collected %d jobs (%d unique by id)", len(all_jobs), unique_ids)

    if args.dry_run:
        new_count, _ = process_jobs(all_jobs, args.db, dry_run=True)
        logger.info(
            "DRY RUN: would insert %d new jobs (out of %d found, %d unique)",
            new_count,
            len(all_jobs),
            unique_ids,
        )
    else:
        inserted, updated = process_jobs(all_jobs, args.db, dry_run=False)
        logger.info("Done: inserted=%d updated=%d", inserted, updated)

    if args.score:
        profile_path = config.get("profile_path", "profile.txt")
        logger.info("--- Semantic Scoring ---")
        try:
            from scoring import run_scoring

            conn = init_db(args.db)
            run_scoring(
                conn=conn,
                profile_path=profile_path,
                threshold=args.threshold,
                rescore_all=args.rescore_all,
            )
            conn.close()
        except FileNotFoundError as e:
            logger.error(str(e))
            sys.exit(1)
        except Exception:
            logger.exception("Scoring failed")


if __name__ == "__main__":
    main()
