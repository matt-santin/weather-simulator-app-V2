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
  contrastCity,
  loadConfig,
  normals,
  search,
  seasonKinds,
  SearchError,
  summaryOf,
  years as everyYear,
} from "./fetch.js";
import { legend, showTemperature, sources, strip, temperaturePick } from "./band.js";
import { refuse } from "./bounds.js";
import { chart } from "./chart.js";
import { attachZoom } from "./dayzoom.js";
import { diagram, snow as snowOf, summary, years as yearsOf } from "./climate.js";
import { alignByDate, gapTone, referenceYears } from "./compare.js";
import { applyTexts, el } from "./dom.js";
import { wireHints } from "./hint.js";
import { decimal, detail, tiles } from "./matrix.js";
import { texts } from "./i18n.js";
import * as present from "./present.js";
import { elevationOf, insideMap, MAP_LATITUDE, mapHref, seasonOfDay, seasonYear } from "./links.js";
import { fillNav } from "./nav.js";
import { DRAWN, drawAnother, kindLabels, kindsOf } from "./kinds.js";
import { dominantSeason, rangeOf, yearsFor } from "./season.js";
import { content as shareCard } from "./sharecard.js";
import { wireShare } from "./sharing.js";
import {
  allValues, degrees, nextSeason, previousSeason, recordPick, recordWords, typical, typicalSpan,
} from "./suggest.js";
import { figures as summaryFigures, heading as summaryHeading, snowFigure, standing } from "./summary.js";

const place = document.getElementById("place");
const altitudeLine = document.getElementById("altitude");
const altitudeText = document.getElementById("altitude-text");
const altitudeMethod = document.getElementById("altitude-method");
const summaryMap = document.getElementById("summary-map");
const ways = document.getElementById("ways");
const range = document.getElementById("range");
const count = document.getElementById("count");
const warning = document.getElementById("warning");
const note = document.getElementById("humid-note");
const snowCoverRow = document.getElementById("snow-cover");
const snowCoverText = document.getElementById("snow-cover-text");
const snowCoverMethod = document.getElementById("snow-cover-method");
const soilNote = document.getElementById("soil-note");
const soilNoteText = document.getElementById("soil-note-text");
const soilNoteMethod = document.getElementById("soil-note-method");
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
// The reference period of the normals, the summary, the climate diagram and the
// matrix: 1991-2020, `normals_default` of /api/config, the one period offered
// since 17/11/2026 (the API still serves the others). Set by `offer`.
let referenceFirst = "";
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
const climateSnowRow = document.getElementById("climate-snow-row");
const climateSnow = document.getElementById("climate-snow");
const climateSnowMethod = document.getElementById("climate-snow-method");
const climateStatus = document.getElementById("climate-status");
const climateFailure = document.getElementById("climate-failure");

const yearsSection = document.getElementById("years");
const yearsTitle = document.getElementById("years-title");
const yearsIntro = document.getElementById("years-intro");
const yearsGrid = document.getElementById("years-grid");
const yearsDetail = document.getElementById("years-detail");
const yearsHeading = document.getElementById("years-heading");
const yearsClose = document.getElementById("years-close");
const yearsLines = document.getElementById("years-lines");

// The icons of the lines of a year, in colour (18/11/2026): a thermometer, a
// cloud and its rain. Named for screen readers, which would otherwise read the
// emoji's own name.
const YEAR_ICONS = { temperature: "\u{1F321}\uFE0F", rain: "\u{1F327}\uFE0F" };

function yearIcon(kind) {
  const label = kind === "rain" ? texts.years.iconRain : texts.years.iconTemperature;
  return el("span", { className: "years-icon", text: YEAR_ICONS[kind], attrs: { role: "img", "aria-label": label } });
}
const yearsSimulated = document.getElementById("years-simulated");
const yearsLink = document.getElementById("years-link");
const yearsStatus = document.getElementById("years-status");
const yearsFailure = document.getElementById("years-failure");

const summarySection = document.getElementById("summary");
const summaryTitle = document.getElementById("summary-title");
const summaryMethod = document.getElementById("summary-method");
const summaryList = document.getElementById("summary-figures");
const summaryStatus = document.getElementById("summary-status");
const summaryRank = document.getElementById("summary-rank");

const summaryKind = document.getElementById("summary-kind");
const summaryKindText = document.getElementById("summary-kind-text");
const summaryRedraw = document.getElementById("summary-redraw");

/**
 * The season came from "Choisir un type de saison" (?type&epoque, written by
 * the home form): the summary says which kind of which epoch, and for a kind
 * drawn at random offers another year of it. An address without them, or with
 * values the form does not offer, shows nothing.
 */
function showKind(config) {
  const season = document.body.dataset.season;
  const kind = query.get("type");
  const epoch = config.epochs.find((e) => e.id === query.get("epoque"));
  const label = kindLabels(season)[kind];
  if (!epoch || !label || !kindsOf(season).includes(kind) || !wholeSeason(asked.start, asked.end)) return;
  const words = texts.summary;
  const of = words.epochOf[epoch.id] ?? "";
  const drawn = DRAWN.includes(kind);
  summaryKindText.textContent = drawn
    ? words.drawn(words.seasons[season][0], label, of, epoch.first, epoch.last)
    : words.fixed(label, of, epoch.first, epoch.last);
  summaryKind.hidden = false;
  if (!drawn) return;
  summaryRedraw.hidden = false;
  summaryRedraw.addEventListener("click", async () => {
    summaryRedraw.disabled = true;
    summaryRedraw.textContent = words.redrawing;
    try {
      const answer = await seasonKinds(asked);
      const ranked = answer.epochs.find((e) => e.id === epoch.id);
      const year = drawAnother(ranked, kind, Number(asked.start.slice(0, 4)));
      const range = year === null ? null : rangeOf(season, year, asked.latitude);
      if (!range) throw new Error("no other year");
      const next = new URLSearchParams(query);
      next.set("debut", range.start);
      next.set("fin", range.end);
      next.delete("jour");
      window.location.assign(`/resultats?${next}`);
    } catch {
      // No other year of this kind, or the server did not answer: the button
      // goes, the season shown stays.
      summaryRedraw.hidden = true;
    }
  });
}

/**
 * The four seasons of the year shown, for the menu on the season word of the
 * summary title: `{ name, label, href, current }`, `href` null for a season
 * without data. Each opens the same place on that season of the same year
 * (the winter of a year runs into the next, as on the home form); the kind it
 * was drawn as and the extreme day are left behind: a record summer says
 * nothing of the autumn after it. Null unless a whole season is shown: dates
 * written by hand get no menu.
 */
let otherSeasons = null;

function offerSeasons(config) {
  const shown = document.body.dataset.season;
  if (!season || !wholeSeason(asked.start, asked.end)) return;
  const year = seasonYear(shown, asked.start, asked.end);
  if (year === null) return;
  otherSeasons = Object.entries(texts.season).map(([name, label]) => {
    const range = rangeOf(name, year, asked.latitude);
    const item = { name, label, href: null, current: name === shown };
    if (item.current || !range || refuse(range, config)) return item;
    const next = new URLSearchParams(query);
    next.set("debut", range.start);
    next.set("fin", range.end);
    for (const key of ["type", "epoque", "jour"]) next.delete(key);
    item.href = `/resultats?${next}`;
    return item;
  });
}

/**
 * The summary title, its season word a button opening the menu of the four
 * seasons when there is one: "[Hiver ▾] 2089-2090 à Paris".
 */
function fillSummaryTitle(shown) {
  const text = summaryHeading(shown, asked.start, asked.end, asked.place);
  const word = texts.season[shown] ?? "";
  if (!otherSeasons || !text.startsWith(word)) {
    summaryTitle.textContent = text;
    return;
  }
  const menu = el(
    "ul",
    { className: "season-menu", attrs: { id: "season-menu", "aria-label": texts.results.seasonSwitch } },
    otherSeasons.map((item) => {
      if (item.current) {
        return el("li", {}, [el("span", { className: "season-item", text: item.label, attrs: { "aria-current": "page" } })]);
      }
      if (!item.href) {
        return el("li", {}, [
          el("span", { className: "season-item", text: `${item.label} (${texts.results.seasonUnavailable})`, attrs: { "aria-disabled": "true" } }),
        ]);
      }
      return el("li", {}, [el("a", { className: "season-item", text: item.label, attrs: { href: item.href } })]);
    }),
  );
  menu.hidden = true;
  const button = el(
    "button",
    {
      className: "season-switch",
      attrs: { type: "button", "aria-expanded": "false", "aria-controls": "season-menu", title: texts.results.seasonSwitch },
    },
    [el("span", { text: word }), el("span", { className: "season-caret", text: "▾", attrs: { "aria-hidden": "true" } })],
  );
  const toggle = (open) => {
    menu.hidden = !open;
    button.setAttribute("aria-expanded", String(open));
  };
  button.addEventListener("click", () => toggle(menu.hidden));
  const wrap = el("span", { className: "season-pick" }, [button, menu]);
  summaryTitle.replaceChildren(wrap, document.createTextNode(text.slice(word.length)));
  closeSeasonMenu = () => toggle(false);
  seasonPick = wrap;
}

// One listener each for the page, whatever the number of times the title is
// drawn: a click outside the menu or Escape closes it.
let closeSeasonMenu = () => {};
let seasonPick = null;
document.addEventListener("click", (event) => {
  if (seasonPick && !seasonPick.contains(event.target)) closeSeasonMenu();
});
document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape" || !seasonPick || seasonPick.querySelector(".season-menu").hidden) return;
  closeSeasonMenu();
  seasonPick.querySelector("button").focus();
});

/** From the 21st to the 20th three months on: a season as the form writes it. */
function wholeSeason(start, end) {
  const months = (Number(end.slice(5, 7)) - Number(start.slice(5, 7)) + 12) % 12;
  return start.slice(8) === "21" && end.slice(8) === "20" && months === 3;
}


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
  elevation: elevationOf(query.get("alt")),
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

// Draws the legend of the calendar for the maxima or the minima, once the
// config is in (show).
let drawLegend = () => {};

async function show(series) {
  wait.hidden = true;
  warning.hidden = !series.has_simulated;
  count.textContent = texts.results.count(series.days.length);
  band.append(...strip(series.days, series.humid_heat_peak));
  foldDays(series.days.length);
  // Maxima by default, minima on demand; not kept from one page to the next.
  const pick = temperaturePick((which) => {
    showTemperature(calendar, which);
    drawLegend(which === "low");
  });
  calendar.prepend(pick.element);
  document.addEventListener("click", (event) => {
    if (!pick.element.contains(event.target)) pick.close();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && pick.isOpen()) pick.close();
  });
  calendar.hidden = false;
  ways.hidden = false;
  attachZoom(band, bandScroll, dayToMap);
  fitCalendar();
  document.fonts?.ready.then(fitCalendar);
  window.addEventListener("resize", fitCalendar);
  humidNote(series.humid_heat_peak);
  const snowLine = present.snowCover(series.snow, series.days);
  if (snowLine) {
    snowCoverText.textContent = snowLine;
    snowCoverMethod.textContent = texts.snow.method(series.has_simulated);
    snowCoverRow.hidden = false;
  }

  // After the strip, always: the days are what the visitor came for, and the
  // drawing waits on a call of its own.
  const config = await settings;
  if (config) {
    scale = { edges: config.temperature_band_edges, step: config.temperature_band_step };
    const snowy = (series.snow?.days ?? 0) > 0;
    drawLegend = (low) => {
      const edges = low ? config.temperature_min_band_edges : config.temperature_band_edges;
      const next = legend(edges, snowy, low);
      const shown = calendar.querySelector(".band-legend");
      if (shown) shown.replaceWith(next);
      else calendar.append(next);
    };
    drawLegend(calendar.dataset.shown === "low");
    drawn = chart(series.days, scale);
    chartPanel.append(drawn);
    chartPanel.hidden = false;
    const soilLine = present.soilLow(series.days);
    if (soilLine) {
      soilNoteText.textContent = soilLine;
      soilNoteMethod.textContent = texts.soil.method(series.has_simulated);
      soilNote.hidden = false;
    }
    offer(series, config);
    offerShare(series, config);
    // The summary card sits above the calendar: the day is sought once it is
    // laid, so that it does not push the day away.
    offerMap(document.body.dataset.season);
    // Before the summary: its title carries the menu of the seasons.
    offerSeasons(config);
    showSummary().finally(() => goToDay(query.get("jour")));
    showKind(config);
    showClimate();
    showYears();
    watchSuggestions(config);
  }

  if (!config) goToDay(query.get("jour"));

  const pairs = sources(series.grid);
  if (pairs.length === 0) {
    provenanceGrid.replaceWith(el("p", { text: texts.provenance.noGrid }));
  } else {
    provenanceGrid.append(...pairs);
  }
  if (series.place_elevation !== null && series.place_elevation !== undefined) {
    const metres = (value) => METRES.format(value);
    altitudeText.textContent = texts.results.altitude(metres(series.place_elevation));
    altitudeMethod.textContent = texts.results.altitudeMethod(
      metres(series.place_elevation),
      metres(series.cell_elevation),
    );
    altitudeLine.hidden = false;
    provenance.append(el("p", {
      text: texts.provenance.altitude(series.place_elevation, series.cell_elevation),
    }));
  }
  provenance.hidden = false;
}

/**
 * On a narrow window the days are a list of one line each, and ninety of them
 * stood between the summary and everything under the calendar. Past the first
 * week they are marked `late`: the sheet hides them there while the list is
 * folded, and the button under it unfolds them. A wide window ignores both.
 */
const FOLDED_DAYS = 7;
const daysMore = document.getElementById("days-more");

function foldDays(total) {
  if (total <= FOLDED_DAYS + 3) return;
  let days = 0;
  for (const item of band.children) {
    if (item.classList.contains("card")) days += 1;
    if (days > FOLDED_DAYS) item.classList.add("late");
  }
  const set = (folded) => {
    band.classList.toggle("is-folded", folded);
    daysMore.setAttribute("aria-expanded", String(!folded));
    daysMore.textContent = folded ? texts.results.daysMore(total) : texts.results.daysLess;
  };
  set(true);
  daysMore.addEventListener("click", () => {
    const folding = !band.classList.contains("is-folded");
    set(folding);
    // Folded from the bottom of ninety lines, the page would be left far below
    // the list: back to its top.
    if (folding) calendar.scrollIntoView({ block: "start" });
  });
  daysMore.parentElement.hidden = false;
}

/** Every day shown, whatever the window: a day sought by the address may be a late one. */
function unfoldDays() {
  if (band.classList.contains("is-folded")) daysMore.click();
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
  const late = card.classList.contains("late");
  if (late) unfoldDays();
  card.classList.add("is-target");
  // The week of the day at the top of the calendar's box, the calendar at the
  // top of the window. At once, not gliding: the focus would stop a smooth
  // scroll halfway.
  const top = card.getBoundingClientRect().top - bandScroll.getBoundingClientRect().top;
  bandScroll.scrollTo({ top: bandScroll.scrollTop + top, behavior: "instant" });
  calendar.scrollIntoView({ block: "start", behavior: "instant" });
  // On the list of a narrow window the calendar's box does not scroll: the
  // day itself is brought into view.
  if (bandScroll.scrollHeight <= bandScroll.clientHeight + 1) {
    card.scrollIntoView({ block: "center", behavior: "instant" });
  }
  card.focus({ preventScroll: true });
}

/**
 * Set the reference period and show the control. The normals exist for every
 * place and date the API serves.
 */
function offer(series, config) {
  referenceFirst = String(config.normals_default);
  compareToggle.addEventListener("click", () => toggle(series));
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
  const reference = referenceFirst;
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

/**
 * One more figure on a winter: snow on the ground, from the climate of the
 * place. It comes from another call than the summary, so it is added when it
 * arrives, if the summary on screen is still the one it was asked for; it
 * failing leaves the summary as it is.
 */
async function addSnow(reference, turn) {
  try {
    const figure = snowFigure(await climateFor(reference));
    if (!figure || turn !== summaryTurn) return;
    summaryList.append(
      el("li", { className: "summary-figure" }, [
        el("p", { className: "summary-value", text: figure.value }),
        el("p", { className: "summary-label", text: figure.label }),
        el("p", { className: "summary-normal", text: figure.normal }),
      ]),
    );
    summaryMethod.textContent += texts.summary.snowMethod;
  } catch {
    // The diagram below says the failure, where the figure comes from.
  }
}

const summaries = new Map();
let summaryTurn = 0;

async function showSummary() {
  const reference = referenceFirst;
  const turn = (summaryTurn += 1);
  try {
    if (!summaries.has(reference)) {
      summaryStatus.textContent = texts.summary.loading;
      summaries.set(reference, await summaryOf(asked, reference));
    }
    if (turn !== summaryTurn) return;
    const answer = summaries.get(reference);
    const shownSeason = document.body.dataset.season;
    fillSummaryTitle(shownSeason);
    // The sentence is for a whole season of the form: other dates have no name
    // to be ranked under.
    const sentence = wholeSeason(asked.start, asked.end)
      ? standing(answer.rank, shownSeason, Number(asked.start.slice(0, 4)) <= (answer.rank?.last ?? 0))
      : "";
    summaryRank.textContent = sentence;
    summaryRank.hidden = sentence === "";
    summaryMethod.textContent =
      texts.summary.method(`${answer.reference_start.slice(0, 4)}-${answer.reference_end.slice(0, 4)}`) +
      (sentence ? texts.summary.rankMethod : "");
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
    if (shownSeason === "winter") addSnow(reference, turn);
  } catch {
    // The summary failing is not the page failing: the days are on screen.
    if (turn === summaryTurn) summarySection.hidden = true;
  } finally {
    if (turn === summaryTurn) summaryStatus.textContent = "";
  }
}

/**
 * The "Partager" pill: the picture and the link of what the page shows. The
 * card is gathered at the click, so that it carries the summary once it is in;
 * without it, the picture has the title and the days.
 */
function offerShare(series, config) {
  const opener = document.getElementById("share-open");
  const dialog = document.getElementById("share");
  if (typeof dialog.showModal !== "function") return;
  wireShare(opener, dialog, () => {
    const shownSeason = document.body.dataset.season;
    const whole = wholeSeason(asked.start, asked.end);
    const answer = summaries.get(referenceFirst);
    const title = whole
      ? summaryHeading(shownSeason, asked.start, asked.end, asked.place)
      : `${asked.place}, ${range.textContent}`;
    return shareCard({
      title,
      rank: summaryRank.hidden ? "" : summaryRank.textContent,
      figures: answer && !summarySection.hidden ? summaryFigures(answer, shownSeason) : [],
      days: series.days,
      simulated: series.has_simulated,
      season: shownSeason,
      edges: config.temperature_band_edges,
      site: texts.nav.home,
      host: window.location.host,
      notAForecast: texts.warning.notAForecast,
    });
  });
  opener.hidden = false;
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
const METRES = new Intl.NumberFormat("fr-FR");

/** The answer of /api/climate for a reference: asked once, by whoever needs it
 * first (the diagram, or the snow of the summary). A failure is not kept. */
function climateFor(reference) {
  if (!climates.has(reference)) {
    const pending = climateOf(asked, reference);
    climates.set(reference, pending);
    pending.catch(() => climates.delete(reference));
  }
  return climates.get(reference);
}
let climateTurn = 0;

/**
 * Draw the climate diagram beside the reference period chosen in the normals
 * menu. A failure stays in its own section: the days are already on screen.
 */
async function showClimate() {
  const reference = referenceFirst;
  const turn = (climateTurn += 1);
  climateFailure.hidden = true;
  climateSection.hidden = false;

  try {
    climateStatus.textContent = texts.climate.loading;
    const answer = await climateFor(reference);
    if (turn !== climateTurn) return;
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
    const snow = snowOf(answer);
    climateSnowRow.hidden = !snow;
    climateSnow.textContent = snow ? snow.line : "";
    climateSnowMethod.textContent = snow ? snow.method : "";
  } catch (error) {
    if (turn !== climateTurn) return;
    climatePanel.replaceChildren();
    climateSnowRow.hidden = true;
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
  const reference = referenceFirst;
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
  const lines = detail(year);
  yearsDetail.dataset.year = String(year.year);
  yearsHeading.textContent = `${year.year} : ${texts.years.heading(
    present.dayMonth(year.start),
    present.dayMonth(year.end),
  ).toLowerCase()}`;
  yearsLines.replaceChildren(
    ...lines.flatMap(({ kind, word, figures }) => [
      yearIcon(kind),
      el("strong", { className: "years-word", text: word }),
      el("span", { className: "years-figures", text: figures }),
    ]),
  );
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

// --- "À voir aussi" ------------------------------------------------------------

const suggestSection = document.getElementById("suggest");
const suggestList = document.getElementById("suggest-list");

/**
 * The block is laid when the climate section nears the window: a visitor who
 * never scrolls down costs no request.
 */
function watchSuggestions(config) {
  const start = () => offerSuggestions(config).catch(() => {
    suggestSection.hidden = true;
  });
  if (!("IntersectionObserver" in window)) {
    start();
    return;
  }
  const watcher = new IntersectionObserver((entries) => {
    if (!entries.some((entry) => entry.isIntersecting)) return;
    watcher.disconnect();
    start();
  }, { rootMargin: "0px 0px 800px 0px" });
  watcher.observe(climateSection);
}

/** Whether every date of a range is past data. */
function isObserved(range, config) {
  return config.periods.some((p) => p.origin === "observed" && range.start >= p.start && range.end <= p.end);
}

/**
 * The address of a season of the same place, or null when it is not served:
 * `{ href, range }`. The kind and the day of the page are left behind, unless
 * given.
 */
function seasonLink(config, name, year, { kind = null, epoch = null, day = null } = {}) {
  const range = rangeOf(name, year, asked.latitude);
  if (!range || refuse(range, config)) return null;
  const next = new URLSearchParams(query);
  next.set("debut", range.start);
  next.set("fin", range.end);
  for (const key of ["type", "epoque", "jour"]) next.delete(key);
  if (kind) {
    next.set("type", kind);
    next.set("epoque", epoch);
  }
  if (day) next.set("jour", day);
  return { href: `/resultats?${next}`, range };
}

/** The cards: `{ kicker, title, line, href }`, in the order they are shown. */
async function suggestions(config) {
  const w = texts.suggest;
  const shownSeason = document.body.dataset.season;
  const whole = wholeSeason(asked.start, asked.end);
  const year = whole ? seasonYear(shownSeason, asked.start, asked.end) : null;
  const [kinds, city] = await Promise.all([
    year !== null ? seasonKinds(asked).catch(() => null) : null,
    contrastCity(asked.latitude, asked.longitude).catch(() => null),
  ]);
  const cards = [];
  const values = allValues(kinds);
  const here = year !== null ? values[year] : undefined;

  if (year !== null) {
    // 1. The next season, or the previous one when the next is not served.
    for (const [step, kicker] of [[nextSeason, w.next], [previousSeason, w.previous]]) {
      const other = step(shownSeason, year);
      const link = other && seasonLink(config, other.season, other.year);
      if (!link) continue;
      cards.push({
        kicker,
        title: summaryHeading(other.season, link.range.start, link.range.end, asked.place),
        href: link.href,
      });
      break;
    }

    // 2. A typical season of the other period.
    const [first, last] = typicalSpan(isObserved(asked, config));
    const pick = typical(values, first, last, year);
    const link = pick && seasonLink(config, shownSeason, pick.year);
    if (link) {
      cards.push({
        kicker: w.typical(texts.summary.seasons[shownSeason][0], first, last),
        title: summaryHeading(shownSeason, link.range.start, link.range.end, asked.place),
        line: w.meanMaximum(degrees(pick.value)) + (here === undefined ? "" : w.against(degrees(here))),
        href: link.href,
      });
    }

    // 3. The record here, or its extreme day.
    const record = recordPick(kinds, shownSeason, year, query.get("type"));
    const recordLink = record && seasonLink(config, shownSeason, record.year, record);
    if (recordLink) {
      const { kicker, line } = recordWords(record, shownSeason);
      cards.push({
        kicker,
        title: record.day
          ? w.dayTitle(present.fullDate(record.day), asked.place)
          : summaryHeading(shownSeason, recordLink.range.start, recordLink.range.end, asked.place),
        line,
        href: recordLink.href,
      });
    }
  }

  // 4. The same dates in a large city of another climate.
  if (city?.name) {
    const there = { latitude: city.latitude, longitude: city.longitude, start: asked.start, end: asked.end };
    const answer = await summaryOf(there, referenceFirst).catch(() => null);
    const value = answer?.figures?.tasmax_mean?.value;
    const mine = summaries.get(referenceFirst)?.figures?.tasmax_mean?.value;
    const address = new URLSearchParams({
      lieu: city.name,
      lat: String(city.latitude),
      lon: String(city.longitude),
      debut: asked.start,
      fin: asked.end,
    });
    cards.push({
      kicker: w.elsewhere,
      title: whole
        ? summaryHeading(shownSeason, asked.start, asked.end, city.name)
        : `${city.name}, ${range.textContent}`,
      line: value === null || value === undefined
        ? ""
        : w.meanMaximum(degrees(value)) + (mine === null || mine === undefined ? "" : w.againstPlace(degrees(mine), asked.place)),
      href: `/resultats?${address}`,
    });
  }
  return cards;
}

async function offerSuggestions(config) {
  const cards = await suggestions(config);
  suggestList.replaceChildren(
    ...cards.map((card) =>
      el("li", {}, [
        el("a", { className: "suggest-card", attrs: { href: card.href } }, [
          el("span", { className: "suggest-kicker", text: card.kicker }),
          el("span", { className: "suggest-name", text: card.title }),
          ...(card.line ? [el("span", { className: "suggest-line", text: card.line })] : []),
          el("span", { className: "suggest-arrow", text: "→", attrs: { "aria-hidden": "true" } }),
        ]),
      ]),
    ),
  );
  // The number of columns of a wide window: one row, whatever the number of cards.
  suggestList.style.setProperty("--cards", String(cards.length));
  suggestSection.hidden = cards.length === 0;
}

/** This page's own URL, on the dates of another year. */
function url({ start, end }) {
  const query = new URLSearchParams({
    lieu: asked.place,
    lat: String(asked.latitude),
    lon: String(asked.longitude),
    debut: start,
    fin: end,
  });
  if (asked.elevation !== null) query.set("alt", String(asked.elevation));
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

function fail(message) {
  wait.hidden = true;
  failure.hidden = false;
  failure.textContent = message;
}
