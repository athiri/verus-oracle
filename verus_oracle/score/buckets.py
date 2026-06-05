from __future__ import annotations

DIFFICULTY_EASY_MAX = 2.5
DIFFICULTY_MEDIUM_MAX = 4.0

DURATION_EASY_MAX_S = 30.0
DURATION_MEDIUM_MAX_S = 120.0


def difficulty_bucket(score: float) -> str:
    if score <= DIFFICULTY_EASY_MAX:
        return "easy"
    if score <= DIFFICULTY_MEDIUM_MAX:
        return "medium"
    return "hard"


def duration_bucket(seconds: float) -> str:
    if seconds <= DURATION_EASY_MAX_S:
        return "easy"
    if seconds <= DURATION_MEDIUM_MAX_S:
        return "medium"
    return "hard"
