"""Deterministic integer quantities used in hashed state."""

from __future__ import annotations

from .core import require


def basis_points(numerator: int, denominator: int) -> int:
    """Round a nonnegative ratio to 0–10,000 basis points without floats."""
    require(isinstance(numerator, int) and not isinstance(numerator, bool)
            and isinstance(denominator, int) and not isinstance(denominator, bool)
            and 0 <= numerator <= denominator and denominator > 0,
            "E-SCHEMA-001", "A basis-point ratio needs 0 <= numerator <= denominator.")
    return (numerator * 10000 + denominator // 2) // denominator
