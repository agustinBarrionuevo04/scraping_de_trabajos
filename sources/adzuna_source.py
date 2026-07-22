from __future__ import annotations

import logging
import os
import time
from typing import Optional

import requests
from tenacity import (
    before_sleep_log,
    retry,
    stop_after_attempt,
    wait_exponential,
)

from models import Job

logger = logging.getLogger(__name__)

ADZUNA_BASE_URL = "https://api.adzuna.com/v1/api/jobs"

LOCATION_COUNTRY_MAP: dict[str, str] = {
    "Argentina": "ar",
    "Córdoba, Argentina": "ar",
    "Spain": "es",
    "Remote": "gb",
}


def _get_location_param(location: str) -> tuple[str, str]:
    country = LOCATION_COUNTRY_MAP.get(location, "gb")
    where = "" if location == "Remote" else location
    return country, where


def _build_job(raw: dict, source: str = "adzuna") -> Optional[Job]:
    try:
        title = (raw.get("title") or "").strip()
        company = (raw.get("company", {}) or {}).get("display_name", "")
        description = (raw.get("description") or "").strip()
        url = (raw.get("redirect_url") or "").strip()
        location_raw = raw.get("location", {}) or {}
        city = location_raw.get("area", [""])[0] if location_raw.get("area") else ""
        country_name = location_raw.get("display_name", "")
        location = f"{city}, {country_name}".strip(", ")

        posted: Optional[str] = raw.get("created")

        salary_min: Optional[float] = raw.get("salary_min")
        salary_max: Optional[float] = raw.get("salary_max")

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
            salary_min=float(salary_min) if salary_min else None,
            salary_max=float(salary_max) if salary_max else None,
        )
    except Exception:
        logger.debug("Failed to normalize adzuna row", exc_info=True)
        return None


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=15),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _fetch_page(
    app_id: str,
    app_key: str,
    country: str,
    what: str,
    where: str,
    page: int,
    results_per_page: int,
) -> list[dict]:
    url = f"{ADZUNA_BASE_URL}/{country}/search/{page}"
    params = {
        "app_id": app_id,
        "app_key": app_key,
        "what": what,
        "where": where,
        "results_per_page": results_per_page,
        "content-type": "application/json",
    }
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("results", [])


def scrape(
    search_terms: list[str],
    locations: list[str],
    results_per_search: int,
    delay_seconds: float,
) -> list[Job]:
    app_id = os.environ.get("ADZUNA_APP_ID", "").strip()
    app_key = os.environ.get("ADZUNA_APP_KEY", "").strip()

    if not app_id or not app_key:
        logger.warning(
            "Adzuna credentials not set (ADZUNA_APP_ID, ADZUNA_APP_KEY). Skipping Adzuna source."
        )
        return []

    all_jobs: list[Job] = []

    for term in search_terms:
        for loc in locations:
            country, where = _get_location_param(loc)
            try:
                logger.info(
                    "adzuna: searching term=%r location=%r country=%s",
                    term,
                    loc,
                    country,
                )
                results = _fetch_page(
                    app_id=app_id,
                    app_key=app_key,
                    country=country,
                    what=term,
                    where=where,
                    page=1,
                    results_per_page=results_per_search,
                )

                if not results:
                    logger.warning(
                        "adzuna returned 0 results for term=%r location=%r",
                        term,
                        loc,
                    )
                    continue

                for raw in results:
                    job = _build_job(raw)
                    if job:
                        all_jobs.append(job)

                logger.info(
                    "adzuna: got %d results for term=%r location=%r",
                    len(results),
                    term,
                    loc,
                )
            except Exception:
                logger.exception(
                    "adzuna failed for term=%r location=%r",
                    term,
                    loc,
                )
            time.sleep(delay_seconds)

    logger.info("adzuna: collected %d total jobs", len(all_jobs))
    return all_jobs
