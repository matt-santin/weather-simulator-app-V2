"""What a search must satisfy before anything is read.

Ninety-two days at most (the longest season at the 21st-to-20th bounds the form
offers), and the whole range inside one served period: a range touching
2026, or straddling 2025 and 2026, is refused whole rather than shown in
part. Where the place is covered is checked against the store, in the endpoint.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, model_validator

from src.app.api import errors
from src.app.store import PERIODS, Period

MAX_DAYS = 92


def periods_text() -> str:
    """The served periods, as the refusal reads them: "1970-2025 et 2027-2100"."""
    return " et ".join(f"{p.start.year}-{p.end.year}" for p in PERIODS)


class Range(BaseModel):
    """The dates of a search, alone: what a map asks for."""

    start: date
    end: date

    @model_validator(mode="after")
    def _check_range(self) -> Range:
        if self.start > self.end:
            raise errors.EmptyRange(self.start, self.end)
        days = (self.end - self.start).days + 1
        if days > MAX_DAYS:
            raise errors.RangeTooLong(days, MAX_DAYS)
        if self.period is None:
            raise errors.Unavailable(self.start, self.end, periods_text())
        return self

    @property
    def period(self) -> Period | None:
        return next((p for p in PERIODS if p.holds(self.start, self.end)), None)


class Search(Range):
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
