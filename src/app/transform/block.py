"""The transformation block: the control point over the weather data.

**Deliberately empty of behaviour.** Later adjustments to the data have one
place to live; what goes in here is a data-treatment decision and belongs to
the project owner.

It runs before the sky class, so that what it changes reaches the pictogram.
It must keep one record per day, in order, leave ``origin`` untouched, and treat
ERA5 and CORDEX days the same way.
"""

from __future__ import annotations

from src.app.domain.records import DailyRecord


def apply(records: list[DailyRecord]) -> list[DailyRecord]:
    """Return the series unchanged.

    The neutral block. Every day of the assembled series passes through here,
    observed and simulated alike, and comes out as it went in.
    """
    return records
