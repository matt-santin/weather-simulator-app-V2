"""The two pages and their files, served by the same application as the API.

``TestClient(app)`` without a context manager runs no lifespan, so the store
is never opened here.

The last test is the one worth having: docs/application.md plans for a static
frontend served by a CDN, so the API must start with no ``web/`` beside it. A
mount written outside that condition would only fail in the deployment nobody
runs locally.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.app.api.app import app, mount_web

WEB = Path(__file__).resolve().parents[1] / "web"


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.mark.parametrize("path", ["/", "/resultats", "/documentation"])
def test_pages_are_served_as_html(client: TestClient, path: str) -> None:
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")


@pytest.mark.parametrize(
    "path",
    [
        "/static/js/fetch.js",
        "/static/js/i18n.js",
        "/static/js/present.js",
        "/static/js/dom.js",
        "/static/js/band.js",
        "/static/js/bounds.js",
        "/static/js/prompt.js",
        "/static/js/home.js",
        "/static/js/results.js",
        "/static/js/season.js",
        "/static/css/style.css",
        "/static/icon.svg",
    ],
)
def test_static_files_are_served(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 200


@pytest.mark.parametrize(
    "path",
    ["/", "/resultats", "/documentation", "/static/js/i18n.js", "/static/css/style.css"],
)
def test_the_browser_is_told_to_ask_before_reusing(client: TestClient, path: str) -> None:
    """No ``Cache-Control`` and the browser invents one.

    Starlette sends an ETag and a Last-Modified but no instruction, so a browser
    falls back on a heuristic and may reuse a module without asking. Invisible in
    production, where nothing moves between two visits; maddening while the
    interface is being worked on, where an edited stylesheet does not arrive.

    ``no-cache`` is not ``no-store``: the copy is kept and an unchanged file
    comes back as a 304. It holds as long as the URLs carry no version.
    """
    assert client.get(path).headers["cache-control"] == "no-cache"


def test_api_still_answers(client: TestClient) -> None:
    """The pages are mounted alongside the API, not in front of it."""
    config = client.get("/api/config")
    assert config.status_code == 200
    assert config.json()["max_days"] == 92


def test_every_season_the_page_can_name_has_a_palette() -> None:
    """The one join between `season.js` and the stylesheet, and it is by name.

    A season the script can write and the sheet cannot paint leaves the page
    with no gradient at all — `--sky` undefined, the sky layer blank. Nothing
    else would catch it: the two files never meet, they only agree.
    """
    sheet = (WEB / "static/css/style.css").read_text()
    # Every name the module can hand back, read off the one table it hands them
    # back from. It used to read the `return "winter"` literals; the table that
    # let the module also *build* a season took them away, and the join is the
    # same join — a name the script can write and the sheet cannot paint.
    written = set(re.findall(r'name: "(\w+)"', (WEB / "static/js/season.js").read_text()))
    painted = set(re.findall(r'body\.results\[data-season="(\w+)"\]', sheet))
    assert written == painted == {"winter", "spring", "summer", "autumn"}


def test_every_season_the_page_can_name_has_a_word() -> None:
    """The second join, and it appeared the day the form offered seasons by name.

    The results page needs a season it can paint; the accueil needs one it can
    *say*, because the select is built from the dictionary. A name in the table
    and not in `texts.season` would be an option with no label — an empty line in
    a list, chosen by nobody, and nothing else would catch it either.
    """
    written = set(re.findall(r'name: "(\w+)"', (WEB / "static/js/season.js").read_text()))
    dictionary = (WEB / "static/js/i18n.js").read_text()
    # The `season:` block alone: `sky` and `measure` sit in the same object and
    # their keys are not seasons.
    block = re.search(r"\n  season: \{(.*?)\n  \},", dictionary, re.DOTALL)
    assert block is not None
    named = set(re.findall(r"(\w+):", block.group(1)))
    assert written == named


def test_the_results_page_carries_a_season_of_its_own() -> None:
    """The fallback for a URL with no usable range, and the only one there is.

    `results.js` writes nothing when it cannot count days, on purpose: two
    fallbacks would be a second place to keep a season name.
    """
    assert 'data-season="summer"' in (WEB / "pages/results.html").read_text()


@pytest.mark.parametrize("page", ["home.html", "results.html", "documentation.html"])
def test_every_in_page_link_lands_somewhere(page: str) -> None:
    """A `href="#x"` with no `id="x"` under it scrolls nowhere, and says nothing.

    Three of these exist and each fails differently if it dangles: the two skip
    links leave a keyboard where it was, and the asterisk after the accueil's
    promise silently stops being a footnote — the one case a reader would not
    even know to report, the mark still being on screen. Nothing else joins the
    two halves; they only agree.
    """
    html = (WEB / "pages" / page).read_text()
    targets = set(re.findall(r'id="([^"]+)"', html))
    anchors = {href for href in re.findall(r'href="#([^"]+)"', html)}
    assert anchors <= targets, f"ancres sans cible dans {page} : {anchors - targets}"


def test_the_footnote_has_both_of_its_marks() -> None:
    """A call with no note is a promise of an explanation that never comes.

    The two halves are in different files and nothing else joins them: the call
    is placed by `home.js`, because it goes *before* the promise's full stop and
    so falls inside a sentence the page never spells out; the note is a line of
    markup in the footer. Drop either and the other goes on rendering, which is
    exactly the failure a reader would not know to report — a star pointing at
    nothing, or a sentence nothing points at.
    """
    script = (WEB / "static/js/home.js").read_text()
    html = (WEB / "pages/home.html").read_text()

    assert '"note-ref"' in script
    assert 'class="note-mark"' in html
    assert 'data-text="warning.note"' in html


def test_the_promise_is_still_a_slot_the_dictionary_fills() -> None:
    """Script marks the promise; it does not become the source of it.

    `pages.test.js` checks page slots against i18n.js, and a promise written
    from `home.js` alone would drop out of that check — and out of the page
    entirely if the script ever failed. The markup keeps the whole sentence,
    unmarked, as what there is to fall back to.
    """
    html = (WEB / "pages/home.html").read_text()
    assert 'id="promise" data-text="home.promise"' in html


# --- the documentation page ---------------------------------------------------
#
# It is the one page whose sentences are not in the dictionary, so it is the one
# page `present.test.js` cannot walk. What that test enforces on every other
# string is enforced here, on the file.


DOCUMENTATION = WEB / "pages/documentation.html"


def documentation_prose() -> str:
    """The page as one line, so a phrase can be looked for in it.

    Every check below asks whether the page *says* something, and the source
    wraps at eighty columns: "le plus élevé" is written with a newline and ten
    spaces inside it, and a search for the phrase misses it. That failure has
    only one direction — the guard passes when the sentence is absent, and goes
    on passing until somebody notices — so the whitespace is flattened once,
    here, rather than at each call.
    """
    return " ".join(DOCUMENTATION.read_text().split())


def test_the_documentation_page_is_reachable_from_both_others() -> None:
    """A page nothing links to is a page nobody reads, and nothing else catches it.

    The route answering 200 says only that the file is served; these two say it
    is offered. Both links are wanted: the accueil's sits under the warning,
    which is where the question arises before any search, and the results
    page's sits outside the warning block on purpose — that block is hidden
    whenever a range stops short of the climate model.
    """
    for page in ("home.html", "results.html"):
        assert 'href="/documentation"' in (WEB / "pages" / page).read_text(), page


def test_the_documentation_page_never_promises_the_day() -> None:
    """No promise of a determined day, in the one file the dictionary test cannot see."""
    prose = documentation_prose().lower()
    for promise in ("il fera", "fera-t-il", "il pleuvra", "il neigera"):
        assert promise not in prose, f'"{promise}" in documentation.html'


def test_the_documentation_page_states_the_model_and_the_scenario() -> None:
    """The reader must know which simulation the future days come from."""
    prose = documentation_prose().replace("&nbsp;", " ")
    for name in ("ERA5", "CORDEX", "EC-EARTH", "RCA4", "RCP 4.5", "intermédiaire"):
        assert name in prose, f"{name} absent de documentation.html"


def test_the_documentation_page_loads_no_script() -> None:
    """It renders with JavaScript off, and that is a property worth holding.

    This is the page a visitor opens to decide whether to trust the other two.
    The day someone adds a module to it, the dictionary rule above stops being a
    deliberate exception and becomes an inconsistency.
    """
    assert "<script" not in DOCUMENTATION.read_text()


def test_nothing_is_mounted_without_the_web_directory(tmp_path) -> None:
    """No pages, no mount, and no exception either."""
    bare = FastAPI()
    assert mount_web(bare, tmp_path / "absent") is False
    assert TestClient(bare).get("/").status_code == 404
