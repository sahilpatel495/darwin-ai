"""Confidence from observable signals, with the reasons spelled out."""

from __future__ import annotations

from dataclasses import dataclass

from app.contracts import Confidence


@dataclass
class Signals:
    repairs: int = 0
    cross_check: str = "skipped"  # agreed | disagreed | unavailable | skipped
    fan_out: bool = False
    max_null_fraction: float = 0.0
    min_join_match: float = 1.0
    used_unconfirmed_link: bool = False
    narration_fallback: bool = False
    vetted_metric: bool = False
    truncated: bool = False
    assumptions: int = 0


def score(signals: Signals) -> Confidence:
    """Start at 0.8; agreed +0.15, vetted_metric +0.05; each repair -0.15; disagreed -0.35;
    fan_out -0.25; max_null_fraction >= 0.2 -0.1; min_join_match < 0.8 -0.15; unconfirmed link
    -0.1; narration fallback -0.05; truncated -0.05; assumptions >= 2 -0.05. Clamp 0..1.
    high >= 0.8, medium >= 0.55, else low. Every applied signal adds a plain-English reason."""
    raise NotImplementedError
