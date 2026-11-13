/**
 * The results page: read the URL, run the search, put what comes back on screen.
 *
 * The search travels in the query string rather than in memory, which is what
 * makes the URL shareable and the back button work. Building the cards is
 * band.js; this file is the wiring.
 *
 * `has_simulated` is read from the response, not worked out from the days. The
 * server already answers that question for itself, and it is the fact rule 1 of
 * the V1 CLAUDE.md hangs on.
 *
 * The season is the one thing here decided from the URL rather than from the
 * answer, and deliberately: it is a background, it must be right before the
 * round trips rather than after them, and a refused search deserves its ground
 * as much as a served one.
 *
 * A refusal is shown as the server wrote it, word for word. The API answers in
 * French under a single `message` field whatever the cause, so an interface
 * that rewrote them would only be inventing a second, less accurate version.
 *
 * **The normals are a second call**, `/api/normals`, on the same place and
 * dates: the server reads 1991-2020 at the same cells and smooths it. What this
 * file adds is the wiring: one fetch at most, and a failure that stays in its
 * corner.
 */

import {
  climate as climateOf,
  loadConfig,
  normals,
  search,
  SearchError,
  summaryOf,
  years as everyYear,
} from "./fetch.js";
import { legend, sources, strip } from "./band.js";
import { chart } from "./chart.js";
import { attachZoom } from "./dayzoom.js";
import { diagram, summary, years as yearsOf } from "./climate.js";
import { alignByDate, gapTone, referenceYears } from "./compare.js";
import { toCsv, fileName } from "./csv.js";
import { applyTexts, el } from "./dom.js";
import { wireHints } from "./hint.js";
import { decimal, detail, tiles } from "./matrix.js";
import { texts } from "./i18n.js";
import * as present from "./present.js";
import { insideMap, MAP_LATITUDE, mapHref, seasonOfDay, seasonYear } from "./links.js";
import { fillNav } from "./nav.js";
import { dominantSeason, yearsFor } from "./season.js";
import { figures as summaryFigures, heading as summaryHeading } from "./summary.js";

const place = document.getElementById("place");
const summaryMap = document.getElementById("summary-map");
const ways = document.getElementById("ways");
const range = document.getElementById("range");
const count = document.getElementById("count");
const warning = document.getElementById("warning");
const note = document.getElementById("humid-note");
const wait = document.getElementById("wait");
const failure = document.getElementById("failure");
const calendar = document.getElementById("calendar");
const band = document.getElementById("days");
const bandScroll = document.getElementById("days-scroll");
const chartPanel = document.getElementById("chart-panel");
const provenance = document.getElementById("provenance");
const provenanceGrid = document.getElementById("provenance-grid");

const compare = document.getElementById("compare");
const compareToggle = document.getElementById("compare-toggle");
const compareReference = document.getElementById("compare-reference");
const compareStatus = document.getElementById("compare-status");
const compareMethod = document.getElementById("compare-method");
const compareFailure = document.getElementById("compare-failure");

const climateSection = document.getElementById("climate");
const climatePanel = document.getElementById("climate-panel");
const climateSubtitle = document.getElementById("climate-subtitle");
const climateLegendTemperature = document.getElementById("climate-legend-temperature");
const climateLegendRain = document.getElementById("climate-legend-rain");
const climateLegendReference = document.getElementById("climate-legend-reference");
const climateSummary = document.getElementById("climate-summary");
const climateSummaryReference = document.getElementById("climate-summary-reference");
const climateStatus = document.getElementById("climate-status");
const climateFailure = document.getElementById("climate-failure");

const yearsSection = document.getElementById("years");
const yearsTitle = document.getElementById("years-title");
const yearsIntro = document.getElementById("years-intro");
const yearsGrid = document.getElementById("years-grid");
const yearsDetail = document.getElementById("years-detail");
const yearsHeading = document.getElementById("years-heading");
const yearsClose = document.getElementById("years-close");
const yearsTemperature = document.getElementById("years-temperature");
const yearsRain = document.getElementById("years-rain");
const yearsSimulated = document.getElementById("years-simulated");
const yearsLink = document.getElementById("years-link");
const yearsStatus = document.getElementById("years-status");
const yearsFailure = document.getElementById("years-failure");

const summarySection = document.getElementById("summary");
const summaryTitle = document.getElementById("summary-title");
const summaryMethod = document.getElementById("summary-method");
const summaryList = document.getElementById("summary-figures");
const summaryStatus = document.getElementById("summary-status");

const exportBlock = document.getElementById("export");
const exportButton = document.getElementById("export-button");

applyTexts();
wireHints();

/**
 * The constants the API serves, asked for at once and waited on at the end.
 *
 * It is a second call, and deliberately not one the page hangs on: the chart is
 * a second reading of days the strip already carries in full, so a config that
 * does not arrive costs the drawing and not the results. Hence the failure
 * folded into `null` here rather than thrown — the search has its own refusals
 * to report, and none of them is this one.
 *
 * The ladder, and the reference periods of the normals, are read from it.
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

// The bar: this page's tab now, the map's once the config says there are maps.
const navSeason = {
  current: "place",
  season,
  year: season ? seasonYear(season, asked.start, asked.end) : null,
  place: asked.place,
  placeHref: `${window.location.pathname}${window.location.search}`,
};
fillNav(navSeason);

// textContent, never innerHTML: the name came from the query string, which is
// to say from outside.
place.textContent = asked.place;
range.textContent = texts.results.range(present.fullDate(asked.start), present.fullDate(asked.end));

/** What the chart needs to graduate its axis, and the node it last drew. */
let scale = null;
let drawn = null;

/** The normals, one fetch per reference period at most. */
const kept = new Map();

/**
 * Which request is the current one: the menu can be changed faster than the
 * server answers, and only the latest request may draw.
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

/**
 * Four weeks in view at most, the rest scrolled to.
 *
 * Measured rather than written in the sheet: a week is as tall as its tallest
 * card, which depends on the type, the width, and whether the humid-heat line
 * is reserved. The box is cut under the last whole week that fits, four at
 * most, fewer when the window is too short to show four, never fewer than one.
 * On a narrow window the sheet turns the calendar into a list of one column,
 * and the box is left to its full height: the page scrolls, not a box inside
 * it.
 */
const WEEKS = 4;
const WINDOW_MARGIN = 64;

function fitCalendar() {
  bandScroll.style.maxHeight = "";
  const columns = getComputedStyle(band).gridTemplateColumns.split(" ").length;
  if (columns < 7) return;
  // The tops of the rows of days, in order; the month lines between them are
  // counted in the height but are not weeks.
  const weeks = [
    ...new Set([...band.querySelectorAll(".card, .pad")].map((cell) => cell.offsetTop)),
  ];
  if (weeks.length <= WEEKS) return;
  const gap = parseFloat(getComputedStyle(band).rowGap) || 0;
  const room = window.innerHeight - WINDOW_MARGIN;
  let height = 0;
  for (let week = 1; week <= WEEKS; week += 1) {
    const bottom = rowBottom(weeks[week - 1], gap);
    if (week > 1 && bottom > room) break;
    height = bottom;
  }
  bandScroll.style.maxHeight = `${height}px`;
}

/** Where the row of days starting at `top` ends: the top of what follows, less a gap. */
function rowBottom(top, gap) {
  const next = [...band.children].find((cell) => cell.offsetTop > top);
  return next ? next.offsetTop - gap : band.scrollHeight;
}

async function show(series) {
  wait.hidden = true;
  warning.hidden = !series.has_simulated;
  count.textContent = texts.results.count(series.days.length);
  band.append(...strip(series.days, series.humid_heat_peak));
  calendar.hidden = false;
  ways.hidden = false;
  attachZoom(band, bandScroll, dayToMap);
  fitCalendar();
  document.fonts?.ready.then(fitCalendar);
  window.addEventListener("resize", fitCalendar);
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
    calendar.append(legend(config.temperature_band_edges));
    drawn = chart(series.days, scale);
    chartPanel.append(drawn);
    chartPanel.hidden = false;
    offer(series, config);
    // The summary card sits above the calendar: the day is sought once it is
    // laid, so that it does not push the day away.
    offerMap(document.body.dataset.season);
    showSummary().finally(() => goToDay(query.get("jour")));
    showClimate();
    showYears();
  }

  if (!config) goToDay(query.get("jour"));

  const pairs = sources(series.grid);
  if (pairs.length === 0) {
    provenanceGrid.replaceWith(el("p", { text: texts.provenance.noGrid }));
  } else {
    provenanceGrid.append(...pairs);
  }
  provenance.hidden = false;
}

/**
 * A day of the calendar leads to the map of Europe on that day, the place
 * marked: only when the server has maps, the place is in their frame and the
 * map offers the season of that day. Until the config arrives, nowhere.
 */
const dayToMap = {
  hint: texts.results.dayOnMap,
  config: null,
  accepts(card) {
    const config = this.config;
    if (!config || !card.dataset.date) return false;
    if (!insideMap(config.map_box, asked.latitude, asked.longitude)) return false;
    const { season, year } = seasonOfDay(card.dataset.date);
    return year !== null && yearsFor(season, MAP_LATITUDE, config).includes(year);
  },
  go(card) {
    const day = card.dataset.date;
    window.location.assign(mapHref({ ...asked, ...seasonOfDay(day), day }));
  },
};
settings.then((config) => {
  dayToMap.config = config;
});

/**
 * The day the map sent the visitor back to (?jour): its card in view, outlined
 * and enlarged. A day outside the dates shown is ignored.
 */
function goToDay(day) {
  if (!day) return;
  const card = band.querySelector(`.card[data-date="${CSS.escape(day)}"]`);
  if (!card) return;
  card.classList.add("is-target");
  // The week of the day at the top of the calendar's box, the calendar at the
  // top of the window. At once, not gliding: the focus would stop a smooth
  // scroll halfway.
  const top = card.getBoundingClientRect().top - bandScroll.getBoundingClientRect().top;
  bandScroll.scrollTo({ top: bandScroll.scrollTop + top, behavior: "instant" });
  calendar.scrollIntoView({ block: "start", behavior: "instant" });
  card.focus({ preventScroll: true });
}

/**
 * Fill the menu of reference periods and show the control. The normals exist for
 * every place and date the API serves.
 */
function offer(series, config) {
  compareReference.append(
    ...config.normals.map((reference) =>
      el("option", { text: reference.label, attrs: { value: String(reference.first) } }),
    ),
  );
  compareReference.value = String(config.normals_default);

  compareToggle.addEventListener("click", () => toggle(series));
  // One menu for all three: the normals, the grey of the climate diagram and
  // the colours of the matrix share their period.
  compareReference.addEventListener("change", () => {
    if (shown()) lay(series);
    showSummary();
    showClimate();
    showYears();
  });
  compare.hidden = false;
  // The normals are drawn from the start since 5/11/2026: they are the yardstick
  // a day is read against. The button now takes them off.
  toggle(series);
}

/** Whether the normals are on the chart: the state of the button. */
function shown() {
  return compareToggle.getAttribute("aria-pressed") === "true";
}

/** Press or release the button, and put the normals on the chart or take them off. */
function toggle(series) {
  const opening = !shown();
  compareToggle.setAttribute("aria-pressed", String(opening));

  if (opening) {
    lay(series);
  } else {
    asking += 1; // Anything still in flight has lost its turn.
    compareMethod.hidden = true;
    compareFailure.hidden = true;
    compareStatus.textContent = "";
    redraw(series, null);
  }
}

/** Fetch the chosen normals if they have not been fetched, then redraw. */
async function lay(series) {
  const reference = compareReference.value;
  const turn = (asking += 1);
  compareFailure.hidden = true;

  try {
    if (!kept.has(reference)) {
      compareStatus.textContent = texts.compare.loading;
      kept.set(reference, await normals(asked, reference));
    }
    if (turn !== asking) return;

    const answer = kept.get(reference);
    const years = referenceYears(answer);
    const aligned = alignByDate(series.days, answer.days);
    redraw(series, aligned, texts.compare.legend(years));
    markNormals(series.days, aligned);
    // Shown by its "?" (hint.js), not here.
    compareMethod.textContent = texts.compare.method(years, answer.window_days);
  } catch (error) {
    if (turn !== asking) return;
    // The normals failing is not the page failing: the days the visitor came
    // for are already on screen, and this says so in its own corner.
    redraw(series, null);
    compareMethod.hidden = true;
    compareFailure.hidden = false;
    compareFailure.textContent =
      error instanceof SearchError ? error.message : texts.transport.serviceFailed;
  } finally {
    if (turn === asking) compareStatus.textContent = "";
  }
}

/** The climate diagrams, one fetch per reference period at most. */
/**
 * The gap of each day's maximum and minimum to their normal, in a small box to
 * the right of each figure in the table the enlarged tile shows (dayzoom.js
 * copies the card, so the boxes go on the card itself). Replaced when the
 * reference period changes. Coloured by gapTone.
 */
function markNormals(days, aligned) {
  const cards = band.querySelectorAll(".card");
  cards.forEach((card, index) => {
    // The first two lines of the table: maximum, then minimum (band.js).
    const [high, low] = card.querySelectorAll(".card-detail dd");
    for (const [cell, name] of [[high, "temperature_max"], [low, "temperature_min"]]) {
      if (!cell) continue;
      cell.querySelector(".card-gap")?.remove();
      const normal = aligned[index]?.[name];
      const value = days[index]?.[name];
      if (normal === null || normal === undefined || value === null || value === undefined) continue;
      const gap = Math.round(value - normal);
      cell.append(
        el("span", {
          className: `card-gap ${gapTone(gap)}`,
          text: texts.detail.gap(GAP.format(gap)),
          attrs: { title: texts.detail.gapTitle },
        }),
      );
    }
  });
}

const GAP = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0, signDisplay: "exceptZero" });

// --- the summary card ----------------------------------------------------------

const summaries = new Map();
let summaryTurn = 0;

async function showSummary() {
  const reference = compareReference.value;
  const turn = (summaryTurn += 1);
  try {
    if (!summaries.has(reference)) {
      summaryStatus.textContent = texts.summary.loading;
      summaries.set(reference, await summaryOf(asked, reference));
    }
    if (turn !== summaryTurn) return;
    const answer = summaries.get(reference);
    const shownSeason = document.body.dataset.season;
    summaryTitle.textContent = summaryHeading(shownSeason, asked.start, asked.end, asked.place);
    summaryMethod.textContent = texts.summary.method(
      `${answer.reference_start.slice(0, 4)}-${answer.reference_end.slice(0, 4)}`,
    );
    summaryList.replaceChildren(
      ...summaryFigures(answer, shownSeason).map((figure) =>
        el("li", { className: `summary-figure${figure.tone ? ` ${figure.tone}` : ""}` }, [
          el("p", { className: "summary-value", text: figure.value }),
          el("p", { className: "summary-label", text: figure.label }),
          el("p", { className: "summary-normal", text: figure.normal }),
        ]),
      ),
    );
    summarySection.hidden = false;
  } catch {
    // The summary failing is not the page failing: the days are on screen.
    if (turn === summaryTurn) summarySection.hidden = true;
  } finally {
    if (turn === summaryTurn) summaryStatus.textContent = "";
  }
}

/**
 * The link to the map of the same season, the place marked on it: only when the
 * server has maps, the place is in their frame and the dates are one season's.
 */
async function offerMap(shownSeason) {
  const config = await settings;
  const year = shownSeason ? seasonYear(shownSeason, asked.start, asked.end) : null;
  if (!config || year === null || !insideMap(config.map_box, asked.latitude, asked.longitude)) {
    summaryMap.hidden = true;
    return;
  }
  summaryMap.href = mapHref({ ...asked, season: shownSeason, year });
  summaryMap.hidden = false;
  fillNav({ ...navSeason, mapHref: summaryMap.href });
}

const climates = new Map();
let climateTurn = 0;

/**
 * Draw the climate diagram beside the reference period chosen in the normals
 * menu. A failure stays in its own section: the days are already on screen.
 */
async function showClimate() {
  const reference = compareReference.value;
  const turn = (climateTurn += 1);
  climateFailure.hidden = true;
  climateSection.hidden = false;

  try {
    if (!climates.has(reference)) {
      climateStatus.textContent = texts.climate.loading;
      climates.set(reference, await climateOf(asked, reference));
    }
    if (turn !== climateTurn) return;

    const answer = climates.get(reference);
    const years = yearsOf(answer.window);
    const referenceYears = yearsOf(answer.reference);
    climatePanel.replaceChildren(diagram(answer));
    climateSubtitle.textContent = texts.climate.subtitle(
      years,
      answer.window.source,
      answer.window.origin === "simulated",
    );
    climateLegendTemperature.textContent = texts.climate.legendTemperature(years);
    climateLegendRain.textContent = texts.climate.legendRain(years);
    climateLegendReference.textContent = texts.climate.legendReference(referenceYears);
    climateSummary.textContent = sentence(years, summary(answer.months));
    climateSummaryReference.textContent = sentence(referenceYears, summary(answer.reference_months));
  } catch (error) {
    if (turn !== climateTurn) return;
    climatePanel.replaceChildren();
    climateFailure.hidden = false;
    climateFailure.textContent =
      error instanceof SearchError ? error.message : texts.transport.serviceFailed;
  } finally {
    if (turn === climateTurn) climateStatus.textContent = "";
  }
}

/** The line under the diagram, from its twelve months. */
function sentence(years, { temperature, precipitation, dry }) {
  return texts.climate.summary(
    years,
    present.temperature(temperature),
    String(Math.round(precipitation)),
    dry.map((month) => texts.climate.monthNames[month - 1]),
  );
}

/** The matrices of years, one fetch per reference period at most. */
const matrices = new Map();
let yearsTurn = 0;

/**
 * Draw the matrix of years against the reference period of the bandeau. The
 * year shown in the detail is kept across a change of reference.
 */
async function showYears() {
  const reference = compareReference.value;
  const turn = (yearsTurn += 1);
  yearsFailure.hidden = true;
  yearsSection.hidden = false;
  // textContent: the name came from the query string.
  yearsTitle.textContent = texts.years.title(asked.place);

  try {
    if (!matrices.has(reference)) {
      yearsStatus.textContent = texts.years.loading;
      matrices.set(reference, await everyYear(asked, reference));
    }
    if (turn !== yearsTurn) return;

    const answer = matrices.get(reference);
    const first = answer.years.find((year) => year.temperature_mean !== null);
    yearsIntro.textContent = texts.years.intro(
      present.dayMonth(first.start),
      present.dayMonth(first.end),
      `${answer.reference_start.slice(0, 4)}-${answer.reference_end.slice(0, 4)}`,
      decimal(answer.temperature_normal),
    );
    const shown = Number(yearsDetail.dataset.year);
    const pick = (year, tile, options) => {
      for (const other of yearsGrid.querySelectorAll("[aria-pressed]")) {
        other.setAttribute("aria-pressed", "false");
      }
      tile.setAttribute("aria-pressed", "true");
      describe(answer, year, tile, options);
    };
    const made = tiles(answer, pick);
    // The year on screen, ringed: the matrix says where it falls among the others.
    const searched = answer.years.findIndex((year) => year.year === Number(asked.start.slice(0, 4)));
    if (searched >= 0) {
      made[searched].classList.add("current");
      made[searched].setAttribute("aria-current", "true");
    }
    yearsGrid.replaceChildren(...made);
    // A window open before a change of reference stays open, on the new tiles,
    // without taking the focus from the menu.
    const again = answer.years.findIndex((year) => year.year === shown);
    if (again >= 0 && answer.years[again].temperature_mean !== null) {
      pick(answer.years[again], made[again], { focus: false });
    }
  } catch (error) {
    if (turn !== yearsTurn) return;
    yearsGrid.replaceChildren();
    yearsFailure.hidden = false;
    yearsFailure.textContent =
      error instanceof SearchError ? error.message : texts.transport.serviceFailed;
  } finally {
    if (turn === yearsTurn) yearsStatus.textContent = "";
  }
}

/** The detail of the year clicked, in its window, anchored to `tile`. */
function describe(answer, year, tile, { focus = true } = {}) {
  const [temperature, rain] = detail(answer, year);
  yearsDetail.dataset.year = String(year.year);
  yearsHeading.textContent = `${year.year} : ${texts.years.heading(
    present.dayMonth(year.start),
    present.dayMonth(year.end),
  ).toLowerCase()}`;
  yearsTemperature.textContent = temperature;
  yearsRain.textContent = rain ?? "";
  yearsSimulated.hidden = year.origin !== "simulated";
  yearsLink.href = url(year);
  yearsLink.textContent = texts.years.see(year.year);
  yearsDetail.hidden = false;
  anchor = tile;
  placeDetail();
  if (focus) yearsClose.focus();
}

/** The tile the window belongs to, while it is open. */
let anchor = null;

/**
 * Put the window over its tile, centred on it and inside the section; under
 * the tile when there is no room above it.
 */
function placeDetail() {
  if (!anchor || yearsDetail.hidden) return;
  const frame = yearsSection.getBoundingClientRect();
  const tile = anchor.getBoundingClientRect();
  const width = yearsDetail.offsetWidth;
  const height = yearsDetail.offsetHeight;
  const gap = 8;

  const centre = tile.left - frame.left + tile.width / 2;
  const left = Math.max(gap, Math.min(centre - width / 2, frame.width - width - gap));
  const above = tile.top - frame.top - height - gap;
  const room = tile.top - height - gap >= 0; // room in the viewport above the tile
  const top = room && above >= 0 ? above : tile.bottom - frame.top + gap;

  yearsDetail.style.left = `${Math.round(left)}px`;
  yearsDetail.style.top = `${Math.round(top)}px`;
}

/** Close the window, release the tile, and give it the focus back if the window had it. */
function closeDetail() {
  if (yearsDetail.hidden) return;
  const had = yearsDetail.contains(document.activeElement);
  yearsDetail.hidden = true;
  delete yearsDetail.dataset.year;
  anchor?.setAttribute("aria-pressed", "false");
  if (had) anchor?.focus();
  anchor = null;
}

yearsClose.addEventListener("click", closeDetail);
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeDetail();
});
document.addEventListener("click", (event) => {
  if (yearsDetail.hidden) return;
  if (yearsDetail.contains(event.target) || event.target.closest?.(".year-tile")) return;
  closeDetail();
});
window.addEventListener("resize", placeDetail);

/** This page's own URL, on the dates of another year. */
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

/**
 * Draw the chart again, with the normals or without them.
 *
 * A whole new node rather than a patch: the temperature window is framed on both
 * series at once, so adding or dropping the normals moves the axis, its
 * graduation and every mark on it. There is nothing in the old drawing worth
 * keeping.
 */
function redraw(series, compared, label = null) {
  const next = chart(series.days, scale, { compared, label });
  drawn.replaceWith(next);
  drawn = next;
}

/**
 * What the visitor takes away: the days on screen.
 *
 * **The normals are not in the file.** They are not days: a row of means dated
 * 14 July would be read, in a spreadsheet years later, as a 14 July that
 * happened.
 */
function take(series) {
  download(toCsv(series.days), fileName(asked.place, asked.start, asked.end));
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

function fail(message) {
  wait.hidden = true;
  failure.hidden = false;
  failure.textContent = message;
}
