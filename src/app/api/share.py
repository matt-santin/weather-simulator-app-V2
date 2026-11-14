"""What a shared link shows before anyone opens it: a title, a sentence, a picture.

The pages write their words in the browser, and the robots that draw a link's
preview (messaging, social networks) run no script: they read the head of the
page as the server sends it. So the server fills that head.

- A search: "Été 2075 à Paris", a sentence made of the figures of the summary
  (summary.run) that says "simulation" for a simulated season, and the season
  as a picture: one tile per day, in the colours of the calendar.
- The other pages: the name of the site, its promise, one picture for all.

Nothing here is trusted from the address: a place name is escaped where it is
written (app.fill), dates and coordinates go through the checks of a search,
and anything refused falls back to the words of the site.

The picture is a PNG written by hand (zlib and numpy): the server needs no
imaging library for flat tiles.
"""

from __future__ import annotations

import struct
import zlib
from datetime import date

import numpy as np
from pydantic import ValidationError

from src.app.api import errors, normals, summary, validation
from src.app.domain import temperature
from src.app.store import Store

SITE = "Météo 2100"
PROMISE = ("Simulez la météo du futur, consultez celle du passé : la météo jour par jour, "
           "partout en Europe, de 1970 à 2100.")
NOT_A_FORECAST = "Simulation : une météo plausible, pas une prévision."

# The first day of each season of the form (web/static/js/season.js): the 21st,
# to the 20th three months later.
SEASONS = {(3, 21): "Printemps", (6, 21): "Été", (9, 21): "Automne", (12, 21): "Hiver"}
MONTHS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
          "septembre", "octobre", "novembre", "décembre")

# The ten colours of the calendar's tiles (web/static/css/style.css, data-band),
# band 0 first; tests/test_pages.py holds the two lists equal.
TILES = ("#2b59c3", "#5c95e8", "#62c6c4", "#9fd77f", "#f7e15f",
         "#fdb342", "#f26b38", "#c81d25", "#5a0b2f", "#1a1a1a")
# A light ground: the tile of 40 °C and more is near black, and must be seen.
GROUND = "#f3f5f9"
GAP_TILE = "#d5d9e0"  # a day without value
WIDTH, HEIGHT = 1200, 630  # the size the previews are drawn at


def decimal(value: float, digits: int = 1) -> str:
    return f"{value:.{digits}f}".replace(".", ",")


def day(d: date) -> str:
    return f"{d.day}{'er' if d.day == 1 else ''} {MONTHS[d.month - 1]} {d.year}"


def season_title(start: date, end: date) -> str | None:
    """"Été 2075", "Hiver 2080-2081", or None when the dates are not a season of the form."""
    name = SEASONS.get((start.month, start.day))
    if name is None or end.day != 20 or (end.month - start.month) % 12 != 3 or end.year - start.year > 1:
        return None
    return f"{name} {start.year}" if start.year == end.year else f"{name} {start.year}-{end.year}"


def searched(store: Store, latitude, longitude, start, end):
    """The search of an address and its cell, or None for anything a search refuses."""
    try:
        search = validation.Search(latitude=latitude, longitude=longitude, start=start, end=end)
    except (ValidationError, errors.ApiError, TypeError, ValueError):
        return None
    cell = store.cell(search.latitude, search.longitude)
    return None if cell is None else (search, cell)


def words(store: Store, place: str | None, latitude, longitude, start, end) -> tuple[str, str]:
    """The title and the sentence of a results page."""
    found = searched(store, latitude, longitude, start, end)
    place = (place or "").strip()[:80]
    if found is None:
        return f"{place} · {SITE}" if place else SITE, PROMISE
    search, cell = found
    when = season_title(search.start, search.end) or f"Du {day(search.start)} au {day(search.end)}"
    title = f"{when} à {place}" if place else when
    figures = summary.run(store, cell, search.start, search.end, normals.DEFAULT).figures
    parts = []
    tx = figures.get("tasmax_mean")
    if tx and tx.value is not None:
        text = f"maximales de {decimal(tx.value)} °C en moyenne"
        if tx.normal is not None:
            gap = tx.value - tx.normal
            text += f" ({'+' if gap >= 0 else '−'}{decimal(abs(gap))} °C par rapport à 1991-2020)"
        parts.append(text)
    hot = figures.get("hot_35")
    if hot and hot.value:
        n = round(hot.value)
        parts.append(f"{n} jour{'s' if n > 1 else ''} à 35 °C ou plus")
    frost = figures.get("frost_days")
    if frost and frost.value and not (hot and hot.value):
        n = round(frost.value)
        parts.append(f"{n} jour{'s' if n > 1 else ''} de gel")
    sentence = f"{title} : {', '.join(parts)}." if parts else f"{title}."
    if search.period.source == "cordex":
        sentence += " " + NOT_A_FORECAST
    return f"{title} · {SITE}", sentence


# --- the picture ---------------------------------------------------------------


def rgb(colour: str) -> tuple[int, int, int]:
    return tuple(int(colour[k:k + 2], 16) for k in (1, 3, 5))


def png(pixels: np.ndarray) -> bytes:
    """An image (rows, columns, 3) of 8-bit colours as a PNG file."""
    rows, columns, _ = pixels.shape
    # Each line opens on its filter: 0, the bytes as they are.
    lines = np.concatenate([np.zeros((rows, 1), "uint8"), pixels.reshape(rows, columns * 3)], axis=1)

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", columns, rows, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(lines.tobytes(), 9))
            + chunk(b"IEND", b""))


def tiles(values: list[float | None], first: date) -> np.ndarray:
    """The days as a calendar on its side: one column per week, Monday on top,
    one tile per day in the colour of its maximum."""
    weeks = (first.weekday() + len(values) + 6) // 7
    gap = 8
    side = min((WIDTH - 2 * 40 + gap) // max(weeks, 1) - gap, (HEIGHT - 2 * 40 + gap) // 7 - gap)
    left = (WIDTH - (weeks * (side + gap) - gap)) // 2
    top = (HEIGHT - (7 * (side + gap) - gap)) // 2
    image = np.empty((HEIGHT, WIDTH, 3), "uint8")
    image[:] = rgb(GROUND)
    for k, value in enumerate(values):
        position = first.weekday() + k
        x, y = left + (position // 7) * (side + gap), top + (position % 7) * (side + gap)
        band = temperature.band(value)
        image[y:y + side, x:x + side] = rgb(GAP_TILE if band is None else TILES[band])
    return image


def card(store: Store, latitude, longitude, start, end) -> bytes | None:
    """The picture of a search, or None for anything a search refuses."""
    found = searched(store, latitude, longitude, start, end)
    if found is None:
        return None
    search, cell = found
    values = store.series(search.period.source, cell, search.start, search.end, ("tasmax",))["tasmax"]
    return png(tiles(values, search.start))
