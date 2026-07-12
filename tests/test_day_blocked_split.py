"""
Tests for the day-blocked split invariant.

Run with:
    python -m pytest tests/test_day_blocked_split.py -v
"""

from datetime import date

import numpy as np

from day_blocked_split import day_blocked_masks


def test_no_day_straddles_folds():
    """A calendar day must never contribute rows to both folds."""
    days = np.array([date(2012, 6, d) for d in range(1, 31) for _ in range(7)])
    train_mask, test_mask = day_blocked_masks(days)

    train_days = set(days[train_mask])
    test_days = set(days[test_mask])
    assert train_days.isdisjoint(test_days)
    assert train_mask.sum() + test_mask.sum() == len(days)
    assert not np.any(train_mask & test_mask)


def test_split_fraction_and_determinism():
    days = np.array([date(2012, 7, 1 + d % 28) for d in range(280)])
    tr1, te1 = day_blocked_masks(days)
    tr2, te2 = day_blocked_masks(days)

    assert np.array_equal(te1, te2)  # seeded → deterministic
    # ~20% of days in test; row fraction close since days are uniform here
    assert 0.1 <= te1.mean() <= 0.3
