from __future__ import annotations

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

ROLE_PATTERNS: dict[str, list[str]] = {
    "trainee": [
        r"\btrainee\b",
        r"\bpasant[íi]a\b",
        r"\bpasante\b",
        r"\bintern\b",
        r"\bprograma de j[óo]venes\b",
        r"\bpractice\b",
    ],
    "jr": [
        r"\bjr\b",
        r"\bjunior\b",
        r"\bj[úu]nior\b",
        r"\bassociate\b",
        r"\bentry[- ]level\b",
        r"\bintroducci[óo]n\b",
    ],
    "mid": [
        r"\bmid[- ]senior\b",
        r"\bmidsenior\b",
        r"\bmiddle\b",
        r"\bmid[- ]level\b",
    ],
    "ssr": [
        r"\bssr\b",
        r"\bssr[-/]\b",
        r"\bsemi[- ]senior\b",
    ],
    "sr": [
        r"\bsr\b",
        r"\bs[ée]nior\b",
        r"\bsenior\b",
        r"\blead\b",
    ],
}

_ROLE_COMPILED: dict[str, list[re.Pattern]] = {
    role: [re.compile(p, re.IGNORECASE) for p in patterns]
    for role, patterns in ROLE_PATTERNS.items()
}

ROLE_ORDER = ["sr", "mid", "ssr", "jr", "trainee"]


def _detected_role(title: str) -> Optional[str]:
    cleaned = re.sub(r"[^a-zúñáéíóü ]", " ", title.lower())
    for role in ROLE_ORDER:
        for pattern in _ROLE_COMPILED[role]:
            if pattern.search(cleaned):
                return role
    return None


def filter_by_role(title: str, roles: list[str]) -> bool:
    roles_lower = [r.strip().lower() for r in roles if r and r.strip()]
    if not roles_lower:
        return True

    if "todos" in roles_lower:
        return True

    detected = _detected_role(title)

    if detected is None:
        return "sin-prefijo" in roles_lower

    return detected in roles_lower
