/**
 * The form: fill in what the API needs that the visitor did not type.
 *
 * Three things. The date fields get their bounds from `/api/config`, so the
 * interface refuses what the API refuses instead of keeping a second copy of
 * the numbers — the V1 CLAUDE.md rule 3. The place name becomes coordinates, because
 * `/api/plan` asks for a latitude and a longitude and a name is not one. And a
 * season asked for by name becomes those same two dates.
 *
 * **The visitor picks the place, this file never picks for them.** Geocoding
 * answers with candidates, not an answer: there are eight Saint-Denis in France
 * and a Paris in Texas. Taking the first would be right most of the time, which
 * is exactly what makes it hard to notice when it is not — so submission stays
 * blocked until a candidate has been chosen.
 *
 * **Both modes write into `debut` and `fin`, two hidden fields.** That is the
 * whole reason the results page did not have to learn anything: the URL is the
 * same five parameters either way, and a season is an interval. The season mode
 * writes them as the visitor picks; the kind mode on submission, once
 * `/api/kinds` has ranked the seasons of the place and one year has been drawn
 * (kinds.js). No `<select>` carries a `name`, so nothing of the modes leaves.
 */

import { covered, geocode, loadConfig, SearchError, seasonKinds } from "./fetch.js";
import { periodsText, refuse } from "./bounds.js";
import { pad } from "./calendar.js";
import { applyTexts, el } from "./dom.js";
import { texts } from "./i18n.js";
import { wireHints } from "./hint.js";
import { anyYearOf, dayOf, draw, epochLabel, kindLabels, kindsOf } from "./kinds.js";
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
const dayField = document.getElementById("jour");
const status = document.getElementById("status");
const placeStatus = document.getElementById("place-status");
const found = document.getElementById("found");
const seasonButton = document.getElementById("mode-season");
const kindButton = document.getElementById("mode-kind");
const seasonPanel = document.getElementById("panel-season");
const kindPanel = document.getElementById("panel-kind");
const seasonPick = document.getElementById("saison");
const yearPick = document.getElementById("annee");
const kindSeasonPick = document.getElementById("saison-type");
const epochPick = document.getElementById("epoque");
const kindPick = document.getElementById("type");
const go = document.getElementById("go");
const coverage = document.getElementById("coverage");

applyTexts();
markPromise(document.getElementById("promise"));
// After markPromise, which builds the asterisk this wires.
wireHints();
// After applyTexts, which fills every other slot: the heading is the one place
// the dictionary is read as a list rather than as a single string.
rotate(document.getElementById("prompt"), texts.home.questions);
fillSeasons();
fillKinds();
// Closed on arrival: the form asks for a place and offers two ways to go on.
show(null);

let config = null;
// Remembered across rebuilds of the list, which happen whenever the season or
// the hemisphere changes: the year is the visitor's choice and should survive a
// list that no longer has the same ends.
let chosenYear = null;

// The bounds, served rather than written here. The years the season mode
// offers and the epochs of the kind mode come from them, which is why those
// lists cannot be built until this arrives.
loadConfig()
  .then((served) => {
    config = served;
    // The first words of the note at the foot of the page: the period covered,
    // which only the config knows. The trailing space belongs here rather than
    // in the markup — it separates this from the sentence in the next span, and
    // leaves the asterisk against the first word on the day the config never
    // arrives and this slot stays empty.
    coverage.textContent = `${texts.warning.coverage(periodsText(served))} `;
    fillYears();
    fillEpochs();
  })
  .catch((error) => say(error.message));

// --- choosing the place ------------------------------------------------------

/**
 * Break the promise into its lines and put the "?" of the note on the dates
 * after its last full stop (hint.js shows the note).
 *
 * The same ringed "?" as the one beside "Type" (since 5/11/2026, in place of
 * an asterisk that read as a footnote call and not as something to touch). The
 * ring keeps it from reading as a question mark closing the promise.
 *
 * The text is read back off the node rather than out of the dictionary a second
 * time: `applyTexts` has just written it.
 */
function markPromise(node) {
  const lines = node.textContent.split("\n");
  node.replaceChildren(
    ...lines.flatMap((line, index) => [
      ...(index > 0 ? [el("br")] : []),
      el("span", { text: line }),
    ]),
    el("button", {
      className: "hint promise-hint",
      text: "?",
      attrs: {
        type: "button",
        "data-hint": "true",
        "aria-controls": "coverage-note",
        "aria-expanded": "false",
        "aria-label": texts.home.noteHint,
      },
    }),
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

// Places offered under the field; twice as many are asked of the geocoder, since
// those outside the domain are dropped.
const OFFERED = 5;

async function propose(name) {
  aboutPlace(texts.form.searching);
  try {
    // `matches`, not `candidates`: that name is the list element above.
    const matches = await geocode(name, config ?? (await loadConfig()));
    // Only the places a search would accept are offered: a name found outside
    // the domain is said here, not after the form has been sent. If the server
    // cannot be asked, every place is offered and the search refuses as before.
    const inside = await covered(matches).catch(() => matches.map(() => true));
    // A slower answer to an older query must not overwrite a newer one.
    if (place.value.trim() !== name) return;
    const shown = matches.filter((_, index) => inside[index]).slice(0, OFFERED);
    offer(shown);
    aboutPlace(
      shown.length > 0 ? "" : matches.length > 0 ? texts.form.outside : texts.form.notFound,
    );
    // Said aloud only. On screen the list is the answer, and counting five
    // visible items back to the reader is noise.
    found.textContent = shown.length ? texts.form.candidates(shown.length) : "";
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

seasonButton.addEventListener("click", () => show("season"));
kindButton.addEventListener("click", () => show("kind"));
kindSeasonPick.addEventListener("change", fillKinds);

seasonPick.addEventListener("change", fillYears);
yearPick.addEventListener("change", () => {
  chosenYear = Number(yearPick.value);
  applySeason();
});

/**
 * Which panel is open: `"season"`, `"kind"`, or none of them.
 *
 * **The third state is the one the page opens on**, and it is the whole point
 * of the two buttons being buttons: the form asks for a place and offers two
 * ways to go on. The submit band goes with the panels: left showing, it would
 * run a search on dates the visitor never saw.
 */
function show(mode) {
  seasonPanel.hidden = mode !== "season";
  kindPanel.hidden = mode !== "kind";
  go.hidden = mode === null;
  seasonButton.setAttribute("aria-pressed", String(mode === "season"));
  kindButton.setAttribute("aria-pressed", String(mode === "kind"));
  if (mode === "season") applySeason();
  say("");
}

/** The four names, from the dictionary, in the order it lists them, in both
 * panels. */
function fillSeasons() {
  const now = seasonOf(today(), Number(latitude.value));
  for (const pick of [seasonPick, kindSeasonPick]) {
    pick.replaceChildren(
      ...Object.entries(texts.season).map(([name, label]) =>
        el("option", { text: label, attrs: { value: name } }),
      ),
    );
    pick.value = now;
  }
}

/** The three kinds, named for the season: a winter is cold or mild. The kind
 * chosen survives a change of season; warm is the default. */
function fillKinds() {
  const chosenKind = kindPick.value || "warm";
  const labels = kindLabels(kindSeasonPick.value);
  kindPick.replaceChildren(
    ...kindsOf(kindSeasonPick.value).map((kind) =>
      el("option", { text: labels[kind], attrs: { value: kind } }),
    ),
  );
  // The extreme day changes with the season: the hottest day becomes the
  // coldest in winter, and the other way round.
  const day = { hottestDay: "coldestDay", coldestDay: "hottestDay" };
  const offered = [...kindPick.options].map((option) => option.value);
  kindPick.value = offered.includes(chosenKind) ? chosenKind : (day[chosenKind] ?? "warm");
}

/** The epochs, as /api/config serves them. */
function fillEpochs() {
  if (!config?.epochs) return;
  epochPick.replaceChildren(
    ...config.epochs.map((epoch) =>
      el("option", { text: epochLabel(epoch), attrs: { value: epoch.id } }),
    ),
  );
  epochPick.value = config.epochs_default;
}

/**
 * The kind mode, on submission: rank the seasons of the place, draw a year of
 * the kind asked for, write its dates, and leave.
 *
 * `form.submit()` does not fire the submit event, so the checks of the listener
 * below are not run twice; the range is still checked against the served
 * periods before leaving.
 */
async function drawSeason(button) {
  const lat = Number(latitude.value);
  const season = kindSeasonPick.value;
  const epoch = config.epochs.find((e) => e.id === epochPick.value);
  const asked = epoch && rangeOf(season, anyYearOf(epoch, yearsFor(season, lat, config)), lat);
  if (!asked) {
    say(texts.form.noYear);
    return;
  }
  button.disabled = true;
  say(texts.form.drawing);
  try {
    const answer = await seasonKinds({
      latitude: latitude.value,
      longitude: longitude.value,
      start: asked.start,
      end: asked.end,
    });
    const ranked = answer.epochs.find((e) => e.id === epoch.id);
    const year = draw(ranked, kindPick.value);
    const range = year === null ? null : rangeOf(season, year, lat);
    if (!range) {
      say(texts.form.noYear);
      return;
    }
    const reason = refuse(range, config);
    if (reason) {
      say(reason);
      return;
    }
    from.value = range.start;
    to.value = range.end;
    const day = dayOf(ranked, kindPick.value);
    dayField.value = day ?? "";
    dayField.disabled = !day;
    form.submit();
  } catch (error) {
    say(error instanceof SearchError ? error.message : texts.transport.serviceFailed);
  } finally {
    button.disabled = false;
  }
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
  // on screen, and with both panels closed there are no dates to send.
  if (kindPanel.hidden && seasonPanel.hidden) {
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
  if (!kindPanel.hidden) {
    event.preventDefault();
    if (!config) {
      say(texts.transport.serviceFailed);
      return;
    }
    drawSeason(go.querySelector("button"));
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
