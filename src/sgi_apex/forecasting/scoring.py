"""Proper scoring rules and calibration diagnostics for sample-based forecasts."""

from __future__ import annotations

from itertools import pairwise

import numpy as np


def crps(samples: np.ndarray, y: float) -> float:
    """CRPS estimated from samples: E|X - y| - 0.5 E|X - X'| (sorted O(n log n) form)."""
    x = np.sort(np.asarray(samples, dtype=float))
    n = len(x)
    term1 = np.mean(np.abs(x - y))
    i = np.arange(1, n + 1)
    term2 = np.sum((2 * i - n - 1) * x) / (n * n)
    return float(term1 - term2)


def interval(samples: np.ndarray, level: float) -> tuple[float, float]:
    a = (1 - level) / 2
    lo, hi = np.quantile(samples, [a, 1 - a])
    return float(lo), float(hi)


def covered(samples: np.ndarray, y: float, level: float) -> bool:
    lo, hi = interval(samples, level)
    return lo <= y <= hi


def brier(p: float, outcome: bool) -> float:
    return float((p - float(outcome)) ** 2)


def log_loss(p: float, outcome: bool, eps: float = 1e-3) -> float:
    p = min(max(p, eps), 1 - eps)
    return float(-np.log(p if outcome else 1 - p))


def reliability(probs: np.ndarray, outcomes: np.ndarray, bins: int = 5) -> list[dict]:
    edges = np.linspace(0, 1, bins + 1)
    out = []
    for lo, hi in pairwise(edges):
        m = (probs >= lo) & ((probs < hi) if hi < 1 else (probs <= hi))
        if m.sum():
            out.append({"bin": f"{lo:.1f}-{hi:.1f}", "n": int(m.sum()),
                        "mean_forecast": float(probs[m].mean()), "observed": float(outcomes[m].mean())})
    return out
