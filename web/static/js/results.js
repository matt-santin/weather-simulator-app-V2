/**
 * The results page: read the URL, run the search, put what comes back on screen.
 *
 * The search travels in the query string rather than in memory, which is what
 * makes the URL shareable and the back button work. Building the cards is
 * band.js; this file is the wiring.
 *
 * `has_simulated` is read from the response, not worked out from the days. The
 * server already answers that question for itself — it is what sends it looking
 * for a cloud-cover correction — and it is the fact CLAUDE.md rule 1 hangs on.
 *
 * The season is the one thing here decided from the URL rather than from the
 * answer, and deliberately: it is a background, it must be right before the four
 * round trips rather than after them, and a refused search deserves its ground
 * as much as a served one.
 *
 * A refusal is shown as the server wrote it, word for word. The API answers in
 * French under a single `message` field whatever the cause, so an interface
 * that rewrote them would only be inventing a second, less accurate version.
 *
 * **The comparison is a second search of the same site**, not a second kind of
 * request: the same dates in another year go back through /api/plan and
 * /api/days, and come back cut, corrected and classified by the same functions.
 * That is what makes the two curves comparable, and it is why nothing was added
 * to the server for it. What this file adds is the wiring: which years may be
 * asked for, one fetch per year at most, and a failure that stays in its corner.
 */

import { loadConfig, search, SearchError } from "./fetch.js";
import { sources, strip } from "./band.js";
import { chart } from "./chart.js";
import { ORDINARY_YEAR, alignByCalendar, selectableYears, shiftRange } from "./compare.js";
import { toCsv, fileName } from "./csv.js";
import { applyTexts, el } from "./dom.js";
import { texts } from "./i18n.js";
import { fullDate } from "./present.js";
import { dominantSeason } from "./season.js";

const place = document.getElementById("place");
const range = document.getElementById("range");
const count = document.getElementById("count");
const warning = document.getElementById("warning");
const note = document.getElementById("humid-note");
const wait = document.getElementById("wait");
const failure = document.getElementById("failure");
const band = document.getElementById("days");
const chartPanel = document.getElementById("chart-panel");
const provenance = document.getElementById("provenance");
const provenanceGrid = document.getElementById("provenance-grid");

const compare = document.getElementById("compare");
const compareToggle = document.getElementById("compare-toggle");
const comparePanel = document.getElementById("compare-panel");
const compareYear = document.getElementById("compare-year");
const compareStatus = document.getElementById("compare-status");
const compareLegend = document.getElementById("compare-legend");
const compareLegendText = document.getElementById("compare-legend-text");
const compareLink = document.getElementById("compare-link");
const compareFailure = document.getElementById("compare-failure");

const exportBlock = document.getElementById("export");
const exportButton = document.getElementById("export-button");

applyTexts();

/**
 * The constants the API serves, asked for at once and waited on at the end.
 *
 * It is a second call, and deliberately not one the page hangs on: the chart is
 * a second reading of days the strip already carries in full, so a config that
 * does not arrive costs the drawing and not the results. Hence the failure
 * folded into `null` here rather than thrown — the search has its own refusals
 * to report, and none of them is this one.
 *
 * The whole answer is kept, not just the ladder: the comparison menu reads the
 * covered period and the maximum range from it, which is the same reason
 * bounds.js gives for taking its numbers from here rather than writing them.
 */
const settings = loadConfig().then(
  (config) => config,
  () => null,
);

const query = new URLSearchParams(window.location.search);
const asked = {
  place: query.get("lieu") ?? "",
  latitude: Number(query.get("lat")),
  longitude: Number(query.get("lon")),
  start: query.get("debut") ?? "",
  end: query.get("fin") ?? "",
};

// The ground, before anything is fetched and before the first paint — this is a
// module, so it runs on the parsed document and the page never shows one season
// then another. Nothing is written when the range is unusable: the markup
// carries a season of its own, and that is the one fallback.
const season = dominantSeason(asked);
if (season) document.body.dataset.season = season;

// textContent, never innerHTML: the name came from the query string, which is
// to say from outside.
place.textContent = asked.place;
range.textContent = texts.results.range(fullDate(asked.start), fullDate(asked.end));

/** What the chart needs to graduate its axis, and the node it last drew. */
let scale = null;
let drawn = null;

/** One fetch per year, at most. Toggling twice costs nothing after the first. */
const kept = new Map();

/**
 * Which comparison is the current one.
 *
 * The menu can be changed faster than Open-Meteo answers, and two answers landing
 * out of order would leave the panel showing one year and the legend naming
 * another. Every request takes a number and only the latest one is allowed to
 * draw.
 */
let asking = 0;

run();

async function run() {
  try {
    const series = await search(asked);
    await show(series);
  } catch (error) {
    fail(error instanceof SearchError ? error.message : texts.transport.serviceFailed);
  }
}

/**
 * The one sentence that explains the mark on the cards, or nothing at all.
 *
 * `humid_heat_peak` arrives on the response rather than being read back off the
 * days, exactly as `has_simulated` does — the server has already been through
 * them. It says two things at once here: whether the strip reserved its line,
 * and which of the two wordings this range has earned.
 *
 * It describes the air and not the reader, which is what puts it out of reach of
 * rule 1 on a simulated day, and it names no survival threshold: that would be a
 * medical claim about a dated day.
 */
function humidNote(peak) {
  if (!peak) return;
  note.append(
    el("span", { text: texts.humidHeat.mark, attrs: { "aria-hidden": "true" } }),
    el("span", { text: ` ${texts.humidHeat.note[peak]} ` }),
    el("a", { text: texts.humidHeat.noteLink, attrs: { href: "/documentation" } }),
  );
  note.hidden = false;
}

async function show(series) {
  wait.hidden = true;
  warning.hidden = !series.has_simulated;
  count.textContent = texts.results.count(series.days.length);
  band.append(...strip(series.days, series.humid_heat_peak));
  humidNote(series.humid_heat_peak);

  // Offered as soon as the days are on screen, and before the chart: what the
  // file carries is the series, and a config that never arrives costs the
  // drawing without costing the days.
  exportButton.addEventListener("click", () => take(series));
  exportBlock.hidden = false;

  // After the strip, always: the days are what the visitor came for, and the
  // drawing waits on a call of its own.
  const config = await settings;
  if (config) {
    scale = { edges: config.temperature_band_edges, step: config.temperature_band_step };
    drawn = chart(series.days, scale);
    chartPanel.append(drawn);
    chartPanel.hidden = false;
    offer(series, config);
  }

  const pairs = sources(series.grid);
  if (pairs.length === 0) {
    provenanceGrid.replaceWith(el("p", { text: texts.provenance.noGrid }));
  } else {
    provenanceGrid.append(...pairs);
  }
  provenance.hidden = false;
}

/**
 * Fill the year menu and show the control — or leave it hidden.
 *
 * A year is offered only when its range has fully passed, so a range too near
 * the far end of the covered period can leave nothing to compare with. The
 * control then does not appear at all: a menu with no year in it would be an
 * offer the page cannot keep.
 */
function offer(series, config) {
  const years = selectableYears(asked, config);
  if (years.length === 0) return;

  compareYear.append(...years.map((year) => el("option", { text: String(year) })));
  // The measured default, when the range allows it. `selectableYears` is walked
  // rather than trusted: a range at the very start of the covered period could
  // leave 1991 out.
  compareYear.value = String(years.includes(ORDINARY_YEAR) ? ORDINARY_YEAR : years.at(-1));

  compareToggle.addEventListener("click", () => toggle(series, config));
  compareYear.addEventListener("change", () => {
    if (!comparePanel.hidden) lay(series, config);
  });
  compare.hidden = false;
}

/** Open or close the panel, and put the other year on the chart or take it off. */
function toggle(series, config) {
  const opening = comparePanel.hidden;
  comparePanel.hidden = !opening;
  compareToggle.setAttribute("aria-expanded", String(opening));
  compareToggle.textContent = opening ? texts.compare.close : texts.compare.open;

  if (opening) {
    lay(series, config);
  } else {
    asking += 1; // Anything still in flight has lost its turn.
    redraw(series, null);
  }
}

/**
 * Fetch the chosen year if it has not been fetched, then redraw.
 *
 * The link is set before the fetch rather than after it: it points at an ordinary
 * search of this site and stays true whether or not the data arrives. It is the
 * accessible equivalent of the two grey curves — the strip on this page writes
 * out one year, and the compared year's own page writes out its own.
 */
async function lay(series, config) {
  const year = Number(compareYear.value);
  const shifted = shiftRange(asked, year, config.max_days);
  const turn = (asking += 1);

  compareLink.href = url(shifted);
  compareLink.textContent = texts.compare.seeYear(year);
  compareFailure.hidden = true;

  try {
    if (!kept.has(year)) {
      compareStatus.textContent = texts.compare.loading;
      const answer = await search({ ...asked, ...shifted });
      kept.set(year, answer.days);
    }
    if (turn !== asking) return;

    redraw(series, alignByCalendar(series.days, kept.get(year)));
    compareLegendText.textContent =
      year === ORDINARY_YEAR ? texts.compare.ordinaryLegend(year) : texts.compare.legend(year);
    compareLegend.hidden = false;
  } catch (error) {
    if (turn !== asking) return;
    // The comparison failing is not the page failing: the days the visitor came
    // for are already on screen, and this says so in its own corner.
    redraw(series, null);
    compareLegend.hidden = true;
    compareFailure.hidden = false;
    compareFailure.textContent =
      error instanceof SearchError ? error.message : texts.transport.serviceFailed;
  } finally {
    if (turn === asking) compareStatus.textContent = "";
  }
}

/**
 * Draw the chart again, with the other year or without it.
 *
 * A whole new node rather than a patch: the temperature window is framed on both
 * series at once, so adding or dropping a year moves the axis, its graduation
 * and every mark on it. There is nothing in the old drawing worth keeping.
 */
function redraw(series, compared) {
  const next = chart(series.days, scale, { compared });
  drawn.replaceWith(next);
  drawn = next;
}

/**
 * What the visitor takes away: the days on screen, and the year laid under them.
 *
 * **The compared year goes in the file when it is on the panel, and only then.**
 * The button says *my data*, which is what is being looked at — a year fetched
 * once and since put away is no longer that. Its rows carry their own dates, so
 * the two years never have to be told apart by a column.
 */
function take(series) {
  const year = Number(compareYear.value);
  const compared = comparePanel.hidden ? [] : (kept.get(year) ?? []);

  download(
    toCsv([...series.days, ...compared]),
    fileName(asked.place, asked.start, asked.end),
  );
}

/**
 * Hand the file to the browser.
 *
 * **The byte order mark is not decoration.** Without it a French spreadsheet
 * reads the accented headers as mojibake, and the reader this file is written
 * for is the one who double-clicks it. It is the same trade the separator makes
 * — `read_csv` wants `encoding="utf-8-sig"` where a spreadsheet wants the mark.
 *
 * The anchor is made, clicked and dropped rather than left in the markup: its
 * href is a blob that does not exist until the button is pressed, and the object
 * URL has to be revoked or the file is held in memory until the page is left.
 */
function download(text, name) {
  const blob = new Blob([`\uFEFF${text}`], { type: "text/csv;charset=utf-8" });
  const href = URL.createObjectURL(blob);
  const link = el("a", { attrs: { href, download: name } });

  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(href);
}

/** The same search, on the compared year — this page's own URL, other dates. */
function url({ start, end }) {
  const query = new URLSearchParams({
    lieu: asked.place,
    lat: String(asked.latitude),
    lon: String(asked.longitude),
    debut: start,
    fin: end,
  });
  return `${window.location.pathname}?${query}`;
}

function fail(message) {
  wait.hidden = true;
  failure.hidden = false;
  failure.textContent = message;
}
