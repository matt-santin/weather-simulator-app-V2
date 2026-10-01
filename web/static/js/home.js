/**
 * The form: fill in what the API needs that the visitor did not type.
 *
 * Three things. The date fields get their bounds from `/api/config`, so the
 * interface refuses what the API refuses instead of keeping a second copy of
 * the numbers — CLAUDE.md rule 3. The place name becomes coordinates, because
 * `/api/plan` asks for a latitude and a longitude and a name is not one. And a
 * season asked for by name becomes those same two dates.
 *
 * **The visitor picks the place, this file never picks for them.** Geocoding
 * answers with candidates, not an answer: there are eight Saint-Denis in France
 * and a Paris in Texas. Taking the first would be right most of the time, which
 * is exactly what makes it hard to notice when it is not — so submission stays
 * blocked until a candidate has been chosen.
 *
 * **The season mode writes into `debut` and `fin` rather than replacing them.**
 * That is the whole reason the results page did not have to learn anything: the
 * URL is the same five parameters either way, `/api/plan` receives an interval
 * as it always has, and a season is an interval. The two `<select>` elements
 * carry no `name`, so nothing of the mode itself leaves this page.
 */

import { geocode, loadConfig, SearchError } from "./fetch.js";
import { periodsText, refuse } from "./bounds.js";
import { DAY, at, iso, pad } from "./calendar.js";
import { applyTexts, el } from "./dom.js";
import { texts } from "./i18n.js";
import { beforeFinalPunctuation } from "./present.js";
import { rotate } from "./prompt.js";
import { rangeOf, seasonOf, yearsFor } from "./season.js";

// The year the form opens on, a simulated one: the site exists to show the
// future. Only a default; the served periods still decide what is refused.
const DEFAULT_YEAR = 2050;

const form = document.getElementById("search");
const place = document.getElementById("lieu");
const candidates = document.getElementById("candidates");
const chosen = document.getElementById("chosen");
const chosenName = document.getElementById("chosen-name");
const change = document.getElementById("change");
const latitude = document.getElementById("lat");
const longitude = document.getElementById("lon");
const from = document.getElementById("debut");
const to = document.getElementById("fin");
const status = document.getElementById("status");
const placeStatus = document.getElementById("place-status");
const found = document.getElementById("found");
const datesButton = document.getElementById("mode-dates");
const seasonButton = document.getElementById("mode-season");
const datesPanel = document.getElementById("panel-dates");
const seasonPanel = document.getElementById("panel-season");
const seasonPick = document.getElementById("saison");
const yearPick = document.getElementById("annee");
const go = document.getElementById("go");
const coverage = document.getElementById("coverage");

applyTexts();
markPromise(document.getElementById("promise"));
// After applyTexts, which fills every other slot: the heading is the one place
// the dictionary is read as a list rather than as a single string.
rotate(document.getElementById("prompt"), texts.home.questions);
fillDefaultDates();
fillSeasons();
// Closed on arrival. The markup ships both panels open so the page works
// without script; this is the line that turns it into a form that unfolds.
show(null);

let config = null;
// Remembered across rebuilds of the list, which happen whenever the season or
// the hemisphere changes: the year is the visitor's choice and should survive a
// list that no longer has the same ends.
let chosenYear = null;

// The bounds, served rather than written here. `min` and `max` let the browser
// refuse an impossible date in its own picker; `refuse()` catches what typing
// gets past it. The years the season mode offers come from the same two bounds,
// which is why that list cannot be built until this arrives.
loadConfig()
  .then((served) => {
    config = served;
    for (const field of [from, to]) {
      field.min = served.coverage_start;
      field.max = served.coverage_end;
    }
    // The first words of the note at the foot of the page: the period covered,
    // which only the config knows. The trailing space belongs here rather than
    // in the markup — it separates this from the sentence in the next span, and
    // leaves the asterisk against the first word on the day the config never
    // arrives and this slot stays empty.
    coverage.textContent = `${texts.warning.coverage(periodsText(served))} `;
    fillYears();
  })
  .catch((error) => say(error.message));

// --- choosing the place ------------------------------------------------------

/**
 * Put the footnote call inside the promise, before its full stop.
 *
 * French typography sets the call ahead of the punctuation, so the sentence has
 * to be cut rather than followed — `beforeFinalPunctuation` decides where, and
 * is tested there because it is arithmetic on a string and this is not.
 *
 * The text is read back off the node rather than out of the dictionary a second
 * time: `applyTexts` has just written it, and reading it twice is the sort of
 * second copy that goes on agreeing with itself while disagreeing with the page.
 *
 * **The mark is not a link, and it is `aria-hidden`.** A link was tried: the
 * note it would have pointed at sits at the foot of a page 960 pixels tall, so
 * a reader on any ordinary window is half a screen from it and the star already
 * says which way to look — the anchor bought nothing and cost a target, a
 * focus stop and a name. Hidden from the accessibility tree for the same
 * reason it is shown to the eye: read aloud, a bare star is "astérisque", which
 * points nowhere. A screen reader gets the whole promise and, further down, the
 * whole note; nothing about the pairing is lost by dropping the mark between
 * them.
 *
 * A span rather than the raw character in the dictionary, because the call is
 * set small and raised, and a substring cannot be styled without an element.
 */
function markPromise(node) {
  // One line per "\n", the call on the last of them — however many that turns
  // out to be. A promise written on a single line gets no break and keeps the
  // mark, which is what this did before the promise had lines at all.
  const lines = node.textContent.split("\n");
  const { body, tail } = beforeFinalPunctuation(lines.pop());
  node.replaceChildren(
    ...lines.flatMap((line) => [el("span", { text: line }), el("br")]),
    el("span", { text: body }),
    el("span", { className: "note-ref", text: "*", attrs: { "aria-hidden": "true" } }),
    el("span", { text: tail }),
  );
}

const PAUSE_MS = 300;
let pending = null;

place.addEventListener("input", () => {
  forget();
  clearTimeout(pending);
  const name = place.value.trim();
  if (name.length < 2) {
    offer([]);
    aboutPlace("");
    return;
  }
  // Not on every keystroke: someone typing "Pontarlier" would fire ten
  // searches, and Open-Meteo counts every one of them against their address.
  pending = setTimeout(() => propose(name), PAUSE_MS);
});

async function propose(name) {
  aboutPlace(texts.form.searching);
  try {
    // `matches`, not `candidates`: that name is the list element above.
    const matches = await geocode(name, config ?? (await loadConfig()));
    // A slower answer to an older query must not overwrite a newer one.
    if (place.value.trim() !== name) return;
    offer(matches);
    aboutPlace(matches.length === 0 ? texts.form.notFound : "");
    // Said aloud only. On screen the list is the answer, and counting five
    // visible items back to the reader is noise.
    found.textContent = matches.length ? texts.form.candidates(matches.length) : "";
  } catch (error) {
    offer([]);
    aboutPlace(error instanceof SearchError ? error.message : texts.transport.serviceFailed);
  }
}

function offer(shown) {
  candidates.replaceChildren(
    ...shown.map((candidate) =>
      el("li", { attrs: { role: "option" } }, [
        el("button", {
          className: "candidate",
          text: describe(candidate),
          attrs: { type: "button" },
        }),
      ]),
    ),
  );
  for (const [index, node] of [...candidates.querySelectorAll("button")].entries()) {
    node.addEventListener("click", () => keep(shown[index]));
  }
  candidates.hidden = shown.length === 0;
  place.setAttribute("aria-expanded", String(shown.length > 0));
}

function keep(candidate) {
  latitude.value = candidate.latitude;
  longitude.value = candidate.longitude;
  place.value = candidate.name;
  chosenName.textContent = texts.form.chosen(describe(candidate));
  chosen.hidden = false;
  place.hidden = true;
  offer([]);
  aboutPlace("");
  found.textContent = "";
  say("");
  // A season belongs to a hemisphere, and the hemisphere just arrived.
  fillYears();
}

/** Back to typing: the coordinates go with the name that produced them. */
function forget() {
  latitude.value = "";
  longitude.value = "";
  chosen.hidden = true;
  place.hidden = false;
  // And it just left again: with no place chosen the reading is the calendar's,
  // exactly as `seasonOf` falls back for a hand-edited URL.
  fillYears();
}

change.addEventListener("click", () => {
  forget();
  place.focus();
  place.select();
});

/** "Paris, Île-de-France, France" — enough to tell two homonyms apart. */
function describe(candidate) {
  return [candidate.name, candidate.admin1, candidate.country].filter(Boolean).join(", ");
}

// --- asking for a season instead of two dates --------------------------------

datesButton.addEventListener("click", () => show("dates"));
seasonButton.addEventListener("click", () => show("season"));

seasonPick.addEventListener("change", fillYears);
yearPick.addEventListener("change", () => {
  chosenYear = Number(yearPick.value);
  applySeason();
});

/**
 * Which period panel is open: `"dates"`, `"season"`, or none of them.
 *
 * **The third state is the one the page opens on**, and it is the whole point
 * of the two buttons being buttons: the form asks for a place and offers two
 * ways to go on, rather than laying out a range nobody asked for. The submit
 * band goes with the panels — left showing, it would run a search on the
 * default fortnight the visitor never saw.
 *
 * Leaving a mode does not put the dates back to their default: the range a
 * season produced is a perfectly good range to adjust by hand, and wiping it
 * would throw away the thing the visitor just asked for.
 */
function show(mode) {
  datesPanel.hidden = mode !== "dates";
  seasonPanel.hidden = mode !== "season";
  go.hidden = mode === null;
  datesButton.setAttribute("aria-pressed", String(mode === "dates"));
  seasonButton.setAttribute("aria-pressed", String(mode === "season"));
  if (mode === "season") applySeason();
  say("");
}

/** The four names, from the dictionary, in the order it lists them. */
function fillSeasons() {
  seasonPick.replaceChildren(
    ...Object.entries(texts.season).map(([name, label]) =>
      el("option", { text: label, attrs: { value: name } }),
    ),
  );
  seasonPick.value = seasonOf(today(), Number(latitude.value));
}

/**
 * The years this season can be asked for, and the dates that follow.
 *
 * Rebuilt rather than filtered, because the list changes with the season *and*
 * with the hemisphere: a northern winter stops at 2049, its far end falling in
 * 2051, and below the equator it is summer that does. The year already chosen is
 * kept when it survives, and pulled back to the nearest end when it does not —
 * silently, because a year vanishing from a list the visitor did not open is not
 * an error to report.
 *
 * Does nothing before `/api/config` has answered: the bounds are its to give,
 * and inventing them here is the copy rule 3 forbids.
 */
function fillYears() {
  if (!config) return;
  const years = yearsFor(seasonPick.value, Number(latitude.value), config);
  if (years.length === 0) return;

  if (chosenYear === null) chosenYear = defaultYear(years);
  chosenYear = Math.min(Math.max(chosenYear, years[0]), years.at(-1));

  yearPick.replaceChildren(
    ...years.map((year) => el("option", { text: String(year), attrs: { value: String(year) } })),
  );
  yearPick.value = String(chosenYear);
  applySeason();
}

/** The season and year, written into the two fields that actually leave. */
function applySeason() {
  // An empty list of years means the config never arrived, and `Number("")` is
  // zero — which `rangeOf` would happily answer with dates in the year 0.
  if (seasonPanel.hidden || !yearPick.value) return;
  const range = rangeOf(seasonPick.value, Number(yearPick.value), Number(latitude.value));
  if (!range) return;
  from.value = range.start;
  to.value = range.end;
  say("");
}

/**
 * The year of the season we are in, which is the year that season *opened* in.
 *
 * Met in January, a northern winter began in the December before it — so the
 * default is one year back. That is read off `rangeOf` rather than written as a
 * rule about winter: the file that owns the boundaries is the one that should
 * answer whether this season has started yet.
 */
function defaultYear(years) {
  const now = today();
  const year = Number(now.slice(0, 4));
  const range = rangeOf(seasonPick.value, year, Number(latitude.value));
  const wanted = range && range.start > now ? year - 1 : year;
  if (years.includes(wanted)) return wanted;
  return years.includes(DEFAULT_YEAR) ? DEFAULT_YEAR : years.at(-1);
}

// --- what leaves, and what does not ------------------------------------------

form.addEventListener("submit", (event) => {
  // Enter in the place field submits a form whether or not a submit button is
  // on screen, and with both panels closed the dates leaving would be the
  // defaults nobody has seen.
  if (datesPanel.hidden && seasonPanel.hidden) {
    event.preventDefault();
    say(texts.form.periodRequired);
    return;
  }
  if (!latitude.value || !longitude.value) {
    event.preventDefault();
    say(texts.form.placeRequired);
    place.hidden = false;
    place.focus();
    return;
  }
  // Without the config there are no bounds to check against, and inventing
  // them here is the copy rule 3 forbids. The API refuses all the same.
  const reason = config && refuse({ start: from.value, end: to.value }, config);
  if (reason) {
    event.preventDefault();
    say(reason);
  }
});

// --- odds and ends -----------------------------------------------------------

/** Refusals and failures that concern the whole search: shown by the button. */
function say(message) {
  status.textContent = message;
}

/** What is happening to the place field: shown beside the place field. */
function aboutPlace(message) {
  placeStatus.textContent = message;
}

/**
 * A fortnight from today, so the page is usable the moment it loads.
 *
 * Only a default in a form field: nothing is displayed from it, the visitor
 * overwrites it freely, and where the observed stops is still decided by the
 * server's clock and not by this one.
 */
function fillDefaultDates() {
  from.value = `${DEFAULT_YEAR}${today().slice(4)}`;
  // Counted in `calendar.js`, where every other day of this project is counted.
  to.value = iso(at(from.value) + 13 * DAY);
}

/**
 * Today, as an ISO day, off this browser's clock.
 *
 * The one local reading in the file, and it has to be local: a visitor in
 * Auckland opening the page on the 3rd should see the 3rd in the field. What
 * happens to that day afterwards is UTC arithmetic like everything else — the
 * server's own clock is what decides where the observed stops, and this only
 * fills a form.
 */
function today() {
  const now = new Date();
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}
