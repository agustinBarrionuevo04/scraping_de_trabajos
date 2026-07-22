from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from sentence_transformers import SentenceTransformer, util

from db import (
    count_above_threshold,
    get_all_jobs,
    get_pending_count,
    get_top_scored,
    get_unscored_jobs,
    update_score,
)

logger = logging.getLogger(__name__)

MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"


def load_profile(profile_path: str) -> str:
    path = Path(profile_path)
    if not path.exists():
        raise FileNotFoundError(f"profile.txt no encontrado en {path.resolve()}")
    content = path.read_text(encoding="utf-8").strip()
    if not content:
        raise ValueError(f"El archivo de perfil {path.resolve()} está vacío")
    logger.info("Profile loaded from %s (%d chars)", profile_path, len(content))
    return content


def load_model() -> SentenceTransformer:
    logger.info("Loading model %s...", MODEL_NAME)
    model = SentenceTransformer(MODEL_NAME)
    logger.info("Model loaded successfully")
    return model


def run_scoring(
    conn: sqlite3.Connection,
    profile_path: str,
    threshold: float,
    rescore_all: bool,
    batch_size: int = 32,
) -> None:
    profile_text = load_profile(profile_path)
    model = load_model()

    logger.info("Encoding profile text...")
    profile_embedding = model.encode(profile_text, convert_to_tensor=True)

    if rescore_all:
        jobs = get_all_jobs(conn)
        logger.info("Rescoring all %d jobs", len(jobs))
    else:
        jobs = get_unscored_jobs(conn)
        logger.info("Found %d unscored jobs", len(jobs))

    if not jobs:
        logger.info("No jobs to score")
        return

    descriptions = [job["description"] for job in jobs]
    ids = [job["id"] for job in jobs]

    logger.info("Encoding %d descriptions (batch_size=%d)...", len(descriptions), batch_size)
    job_embeddings = model.encode(
        descriptions,
        batch_size=batch_size,
        convert_to_tensor=True,
        show_progress_bar=True,
    )

    logger.info("Computing cosine similarities...")
    scores = util.cos_sim(profile_embedding, job_embeddings)[0]

    scored_count = 0
    for i, job_id in enumerate(ids):
        score = float(scores[i])
        update_score(conn, job_id, score)
        scored_count += 1

    logger.info("Scored %d jobs", scored_count)

    pending = get_pending_count(conn)
    above = count_above_threshold(conn, threshold)
    top = get_top_scored(conn, threshold, limit=10)

    logger.info("========================================")
    logger.info("Scoring Summary")
    logger.info("========================================")
    logger.info("Jobs scored this run: %d", scored_count)
    logger.info("Jobs still pending score: %d", pending)
    logger.info("Jobs above threshold (≥%.2f): %d", threshold, above)
    logger.info("========================================")
    if top:
        logger.info("Top 10 matches:")
        for rank, job in enumerate(top, 1):
            logger.info(
                "  %2d. [%.3f] %s — %s (%s)",
                rank,
                job["score"],
                job["title"],
                job["company"],
                job["source"],
            )
    else:
        logger.info("No jobs above threshold (≥%.2f)", threshold)
    logger.info("========================================")
