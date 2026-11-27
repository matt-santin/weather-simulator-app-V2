"""A place name as it is searched (src.store.geocode writes it, src.app.api.geocode reads it)."""

from __future__ import annotations

import unicodedata

# Abbreviations a visitor types: "st jean de luz".
WORDS = {"st": "saint", "ste": "sainte", "sts": "saints", "stes": "saintes"}


def key(name: str) -> str:
    """A name as it is searched: no accents, no case, hyphens and apostrophes as spaces."""
    decomposed = unicodedata.normalize("NFKD", name)
    plain = "".join(c for c in decomposed if not unicodedata.combining(c))
    plain = plain.replace("ß", "ss").replace("ł", "l").replace("Ł", "l").replace("ø", "o").replace("Ø", "o")
    plain = plain.replace("æ", "ae").replace("œ", "oe").replace("đ", "d").replace("ı", "i")
    for mark in "-'’.,()":
        plain = plain.replace(mark, " ")
    return " ".join(WORDS.get(word, word) for word in plain.lower().split())
