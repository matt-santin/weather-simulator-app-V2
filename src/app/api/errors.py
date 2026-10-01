"""Refusals, and the French sentence each one shows. The interface displays them verbatim."""

from __future__ import annotations

from datetime import date


class ApiError(Exception):
    """``message`` is what the visitor reads; the exception string is for logs."""

    status_code = 400

    def __init__(self, detail: str, message: str) -> None:
        super().__init__(detail)
        self.message = message


class EmptyRange(ApiError):
    def __init__(self, start: date, end: date) -> None:
        super().__init__(
            f"empty range: {start} is after {end}",
            "La date de fin précède la date de début.",
        )


class RangeTooLong(ApiError):
    """The bound is passed in by validation, which holds it."""

    def __init__(self, days: int, maximum: int) -> None:
        super().__init__(
            f"{days} days requested, at most {maximum} are served",
            f"Une recherche porte sur {maximum} jours au plus, soit une saison. "
            "Réduisez la plage de dates.",
        )


class Unavailable(ApiError):
    """The range is not inside one served period (store.PERIODS)."""

    def __init__(self, start: date, end: date, periods: str) -> None:
        super().__init__(
            f"{start}..{end} is not inside one served period",
            f"Données indisponibles pour cette période. Les dates disponibles sont {periods}.",
        )


class OutsideDomain(ApiError):
    def __init__(self, latitude: float, longitude: float) -> None:
        super().__init__(
            f"{latitude:.4f}, {longitude:.4f} is outside the domain",
            "Lieu hors de la zone couverte (Europe).",
        )
