from __future__ import annotations

import logging
import time
from typing import Optional

from tenacity import (
    before_sleep_log,
    retry,
    stop_after_attempt,
    wait_exponential,
)

from models import Job

logger = logging.getLogger(__name__)

JOBSPY_SITES = ["linkedin", "indeed", "glassdoor", "zip_recruiter"]


def _safe_str(val) -> str:
    try:
        import math

        import pandas as pd

        if val is None:
            return ""
        if isinstance(val, float) and math.isnan(val):
            return ""
        if isinstance(val, pd._libs.missing.NAType):
            return ""
        if pd.isna(val):
            return ""
        return str(val).strip()
    except ImportError:
        return str(val).strip() if val is not None else ""


def _safe_float(val) -> Optional[float]:
    try:
        import math

        import pandas as pd

        if val is None:
            return None
        if isinstance(val, float) and math.isnan(val):
            return None
        if pd.isna(val):
            return None
        return float(val)
    except (ImportError, TypeError, ValueError):
        if val is None:
            return None
        try:
            return float(val)
        except (TypeError, ValueError):
            return None


def _build_job(raw, source: str) -> Optional[Job]:
    try:
        title = _safe_str(getattr(raw, "title", ""))
        company = _safe_str(getattr(raw, "company", ""))
        description = _safe_str(getattr(raw, "description", ""))
        url = _safe_str(getattr(raw, "job_url", ""))
        location = _safe_str(getattr(raw, "location", ""))

        raw_date = getattr(raw, "date_posted", None)
        posted: Optional[str] = None
        if raw_date is not None:
            date_str = _safe_str(raw_date)
            if date_str:
                posted = date_str

        salary_min = _safe_float(getattr(raw, "min_amount", None))
        salary_max = _safe_float(getattr(raw, "max_amount", None))

        if not title or not company:
            return None

        return Job(
            title=title,
            company=company,
            location=location,
            description=description,
            url=url,
            source=source,
            posted_date=posted,
            salary_min=salary_min,
            salary_max=salary_max,
        )
    except Exception:
        logger.debug("Failed to normalize jobspy row", exc_info=True)
        return None


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=4, min=2, max=30),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _scrape_one(search_term: str, location: str, results_wanted: int, site_filter: list[str]) -> list[Job]:
    from jobspy import scrape_jobs as jobspy_scrape

    logger.info(
        "jobspy: searching term=%r location=%r sites=%s results=%d",
        search_term,
        location,
        site_filter,
        results_wanted,
    )

    df = jobspy_scrape(
        site_name=site_filter,
        search_term=search_term,
        location=location,
        results_wanted=results_wanted,
    )

    if df is None or df.empty:
        logger.warning(
            "jobspy returned 0 results for term=%r location=%r",
            search_term,
            location,
        )
        return []

    jobs: list[Job] = []
    for _, row in df.iterrows():
        source = str(getattr(row, "site", "")).lower()
        if not source:
            continue
        job = _build_job(row, source)
        if job:
            jobs.append(job)

    logger.info("jobspy: got %d normalized jobs", len(jobs))
    return jobs


def scrape(search_terms: list[str], locations: list[str], results_per_search: int, delay_seconds: float) -> list[Job]:
    all_jobs: list[Job] = []

    for term in search_terms:
        for loc in locations:
            try:
                batch = _scrape_one(term, loc, results_per_search, JOBSPY_SITES)
                all_jobs.extend(batch)
            except Exception:
                logger.exception(
                    "jobspy failed for term=%r location=%r",
                    term,
                    loc,
                )
            time.sleep(delay_seconds)

    return all_jobs
