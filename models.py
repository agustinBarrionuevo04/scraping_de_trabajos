from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class Job:
    title: str
    company: str
    location: str
    description: str
    url: str
    source: str
    posted_date: Optional[str] = None
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    scraped_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    match_score: Optional[float] = None
    scored_at: Optional[str] = None

    @property
    def id(self) -> str:
        raw = f"{self.company}|{self.title}|{self.source}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
