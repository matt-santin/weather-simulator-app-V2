/**
 * The map page: one variable over Europe, a season day after day.
 *
 * Four things are fetched: the config (periods, band edges, the simulation
 * served, which names itself in the warning and the source), the land cells and
 * the variables served (once), the country outlines (a static file), and the
 * season itself, as integers; with the isobars ticked, the sea-level pressure
 * of the same days too. How each variable is drawn is in mapview.js
 * (VARIABLES). Everything drawn is read from those; the arithmetic is in
 * mapview.js, this file is the wiring: the period chosen, the map, the panel,
 * the timeline and the player.
 *
 * The way to the results page and back (links.js): a place in the URL (from
 * the results page) is marked, its value of the day is in the panel with a link
 * back to its results; a cell clicked opens a card with the town it is near
 * (/api/place) and a link to the results of that point, on the season shown.
 * Both links carry the day on screen (`jour`), and so does the URL while the
 * player is stopped: a map comes back, or is shared, on its day.
 */

import { DAY, at, iso } from "./calendar.js";
import { applyTexts, el } from "./dom.js";
import { wireHints } from "./hint.js";
import { loadConfig, mapCells, mapDays, mapIsobars, nearestPlace, outlines, SearchError } from "./fetch.js";
import { texts } from "./i18n.js";
import {
  FILL,
  MAX_ZOOM,
  WHOLE,
  band,
  contour,
  day,
  frame,
  grid,
  labelSpots,
  levels,
  pan,
  projection,
  summary,
  unzoom,
  VARIABLES,
  zoomAt,
} from "./mapview.js";
import * as present from "./present.js";
import { insideMap, MAP_LATITUDE, resultsHref } from "./links.js";
import { fillNav } from "./nav.js";
import { rangeOf, yearsFor } from "./season.js";

/** Europe is northern: the seasons are read at this latitude. */
const LATITUDE = MAP_LATITUDE;
/** A press that moves less than this (pixels) is a click, not a drag. */
const CLICK = 5;
/** Country names in French, from their ISO codes (GeoNames gives codes). */
const COUNTRIES = new Intl.DisplayNames(["fr"], { type: "region" });
const SEASONS = ["spring", "summer", "autumn", "winter"];
const DEFAULT = { variable: "tasmax", season: "summer", year: 2100 };
const SPEEDS = [1, 3, 8];

const title = document.getElementById("maps-title");
const variableField = document.getElementById("maps-variable");
const seasonField = document.getElementById("maps-season");
const yearField = document.getElementById("maps-year");
const isobarsField = document.getElementById("maps-isobars");
const isobarsBox = document.getElementById("maps-isobars-field");
const warning = document.getElementById("maps-warning");
const warningNote = document.getElementById("maps-warning-note");
const sourceNote = document.getElementById("maps-source");
const status = document.getElementById("maps-status");
const failure = document.getElementById("maps-failure");
const stage = document.getElementById("maps-stage");
const mapMain = document.getElementById("maps-main");
const player = document.getElementById("maps-player");
const mapCanvas = document.getElementById("map");
const tip = document.getElementById("maps-tip");
const zoomIn = document.getElementById("maps-zoom-in");
const zoomOut = document.getElementById("maps-zoom-out");
const zoomWhole = document.getElementById("maps-zoom-whole");
const dateLine = document.getElementById("maps-date");
const dayLine = document.getElementById("maps-day");
const bandList = document.getElementById("maps-bands");
const playButton = document.getElementById("maps-play");
const prevButton = document.getElementById("maps-prev");
const nextButton = document.getElementById("maps-next");
const speedField = document.getElementById("maps-speed");
const timeline = document.getElementById("maps-timeline");
const pickCard = document.getElementById("maps-pick");
const pickClose = document.getElementById("maps-pick-close");
const pickValue = document.getElementById("maps-pick-value");
const pickName = document.getElementById("maps-pick-name");
const pickWhere = document.getElementById("maps-pick-where");
const pickLink = document.getElementById("maps-pick-link");
const here = document.getElementById("maps-here");
const hereLabel = document.getElementById("maps-here-label");
const hereValue = document.getElementById("maps-here-value");
const hereLink = document.getElementById("maps-here-link");

applyTexts();
wireHints();

const ONE_DECIMAL = new Intl.NumberFormat("fr-FR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const WHOLE_NUMBER = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 });
const PERCENT = new Intl.NumberFormat("fr-FR", { style: "percent", maximumFractionDigits: 0 });
/**
 * A value as the results page writes it: the figure, its unit smaller beside
 * it (the `.unit` of the calendar).
 */
const measureNodes = (value) => [
  document.createTextNode((state.spec.decimals ? ONE_DECIMAL : WHOLE_NUMBER).format(value)),
  el("span", { className: "unit", text: state.spec.unit }),
];
/** A value of the variable on screen, with its unit: "27,2 °C", "12,4 mm", "60 %". */
const measure = (value) =>
  `${(state.spec.decimals ? ONE_DECIMAL : WHOLE_NUMBER).format(value)} ${state.spec.unit}`;
const where = (lat, lon) =>
  `${ONE_DECIMAL.format(Math.abs(lat))}° ${lat >= 0 ? texts.maps.north : texts.maps.south}, ` +
  `${ONE_DECIMAL.format(Math.abs(lon))}° ${lon >= 0 ? texts.maps.east : texts.maps.west}`;

/** What is on screen. */
const state = {
  config: null,
  variable: null,
  spec: null, // VARIABLES[variable]
  edges: [],
  cells: null,
  geometry: null,
  rings: [],
  box: null,
  season: null, // { values, days, cells, start, origin }
  pressure: null, // { values, days, rows, cols, north, west, step, start }, the same days
  lines: null, // the isobars of the day on screen, as drawn
  summaries: [],
  current: 0,
  playing: null,
  hover: null,
  zoom: WHOLE,
  image: null, // { values, canvas, hottest }: the cells of the day on screen
  asking: 0,
  place: null, // { name, latitude, longitude, k }: from the results page, marked
  pick: null, // { latitude, longitude, k, label, turn }: the cell clicked
  wanted: null, // the day of the URL (?jour), shown once its season is loaded
  picking: 0,
};

boot();

async function boot() {
  try {
    const [config, cells, shapes] = await Promise.all([loadConfig(), mapCells(), outlines()]);
    state.config = config;
    warningNote.textContent = texts.maps.simulated(config.simulation);
    sourceNote.textContent = texts.maps.source(config.simulation, cells.isobars);
    state.cells = cells;
    state.geometry = grid(cells);
    state.rings = shapes.rings;
    state.box = shapes.box;
    // Framed on the cells, half a cell and a little sea around them.
    const g = state.geometry;
    state.frame = frame(
      cells.rows.map((_, k) => [g.longitude(k), g.latitude(k)]),
      g.step / 2 + 0.5,
    );
  } catch (error) {
    fail(error);
    return;
  }
  fillSpeeds();
  const asked = fromUrl();
  state.place = asked.place;
  state.wanted = asked.day;
  fillVariables(asked.variable);
  fillPeriod(asked);
  variableField.addEventListener("change", () => {
    choose(variableField.value);
    load();
  });
  seasonField.addEventListener("change", () => {
    fillYears(seasonField.value, Number(yearField.value));
    load();
  });
  yearField.addEventListener("change", load);
  isobarsBox.hidden = !state.cells.isobars;
  isobarsField.checked = state.cells.isobars && asked.isobars;
  isobarsField.addEventListener("change", load);
  wirePlayer();
  wireMap();
  // The column, not the map: maps.js sets the map's width, the layout sets the column's.
  new ResizeObserver(redraw).observe(mapMain);
  window.addEventListener("resize", redraw);
  load();
}

/** The variable, season and year in the URL, or the default. */
function fromUrl() {
  const query = new URLSearchParams(window.location.search);
  const offered = state.cells.variables;
  const variable = offered.includes(query.get("grandeur")) ? query.get("grandeur") : DEFAULT.variable;
  const season = SEASONS.includes(query.get("saison")) ? query.get("saison") : DEFAULT.season;
  const year = Number(query.get("annee")) || DEFAULT.year;
  const day = /^\d{4}-\d{2}-\d{2}$/.test(query.get("jour") ?? "") ? query.get("jour") : null;
  return { variable, season, year, isobars: query.get("isobares") === "1", place: placeOf(query), day };
}

/**
 * The place of the URL (lieu, lat, lon), the one the results page sent, or
 * null; `k` is its cell, undefined over the sea.
 */
function placeOf(query) {
  const name = query.get("lieu");
  const latitude = Number(query.get("lat"));
  const longitude = Number(query.get("lon"));
  if (!name || !query.has("lat") || !query.has("lon")) return null;
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) return null;
  if (!insideMap(state.box, latitude, longitude)) return null;
  return { name, latitude, longitude, k: cellAt(longitude, latitude) };
}

/** The index of the land cell holding a point, or undefined. */
function cellAt(lon, lat) {
  const g = state.geometry;
  const row = Math.floor((g.north - lat) / g.step);
  const col = Math.floor((lon - g.west) / g.step);
  return row >= 0 && col >= 0 && col < g.cols ? g.index.get(row * g.cols + col) : undefined;
}

/** The variables the server has, in the order of VARIABLES. */
function fillVariables(variable) {
  const offered = Object.keys(VARIABLES).filter((name) => state.cells.variables.includes(name));
  variableField.replaceChildren(
    ...offered.map((name) => el("option", { text: texts.maps.variables[name], attrs: { value: name } })),
  );
  variableField.value = offered.includes(variable) ? variable : offered[0];
  choose(variableField.value);
}

/** Make `name` the variable on screen: its scale, its legend. */
function choose(name) {
  state.variable = name;
  state.spec = VARIABLES[name];
  state.edges = state.spec.edges ?? state.config.temperature_band_edges;
  fillBands();
}

function fillPeriod({ season, year }) {
  seasonField.replaceChildren(
    ...SEASONS.map((name) => el("option", { text: texts.season[name], attrs: { value: name } })),
  );
  seasonField.value = season;
  fillYears(season, year);
}

/** The years this season can be shown in; the year kept if it still can. */
function fillYears(season, wanted) {
  const years = yearsFor(season, LATITUDE, state.config);
  yearField.replaceChildren(...years.map((year) => el("option", { text: String(year) })));
  yearField.value = String(years.includes(wanted) ? wanted : years.at(-1));
}

function fillSpeeds() {
  speedField.replaceChildren(
    ...SPEEDS.map((speed) => el("option", { text: texts.maps.speeds[speed], attrs: { value: String(speed) } })),
  );
  speedField.value = "3";
  speedField.addEventListener("change", () => {
    if (state.playing) play(true);
  });
}

/** The legend and the distribution, one line per band. */
function fillBands() {
  const { edges, spec } = state;
  const label = (index) =>
    index === 0
      ? `< ${edges[0]}`
      : index === edges.length
        ? `≥ ${edges.at(-1)}`
        : `${edges[index - 1]} à ${edges[index]}`;
  bandList.replaceChildren(
    ...spec.colors.slice(0, edges.length + 1)
      .map((color, index) =>
        el("li", { className: spec.hatchTop && index === edges.length ? "hottest" : "" }, [
          el("span", { className: "maps-swatch", attrs: { style: `background-color: ${color}`, "aria-hidden": "true" } }),
          el("span", { className: "maps-band-label", text: `${label(index)} ${spec.unit}` }),
          el("span", { className: "maps-bar" }),
          el("span", { className: "maps-share" }),
        ]),
      )
      .reverse(),
  );
}

async function load() {
  const season = seasonField.value;
  const year = Number(yearField.value);
  const range = rangeOf(season, year, LATITUDE);
  const turn = (state.asking += 1);
  play(false);
  const variable = state.variable;
  const isobars = isobarsField.checked;
  const query = { grandeur: variable, saison: season, annee: String(year) };
  if (isobars) query.isobares = "1";
  if (state.place) {
    query.lieu = state.place.name;
    query.lat = String(state.place.latitude);
    query.lon = String(state.place.longitude);
  }
  history.replaceState(null, "", `?${new URLSearchParams(query)}`);
  linkHere();
  title.textContent = texts.maps.title(texts.maps.variables[variable], texts.season[season], year);
  document.title = `${title.textContent} · ${texts.maps.pageTitle}`;
  failure.hidden = true;
  status.textContent = texts.maps.loading;

  try {
    // The pressure of the same days is kept while the season does not change.
    const kept = state.pressure;
    const same = kept && kept.start === range.start && kept.days === state.season?.days;
    const [answer, pressure] = await Promise.all([
      mapDays(variable, range.start, range.end),
      isobars && !same ? mapIsobars(range.start, range.end) : kept,
    ]);
    if (turn !== state.asking) return;
    state.season = answer;
    state.pressure = pressure;
    state.lines = null;
    state.summaries = Array.from({ length: answer.days }, (_, k) =>
      summary(day(answer.values, answer.cells, k), state.edges),
    );
    warning.hidden = answer.origin !== "simulated";
    stage.hidden = false;
    player.hidden = false;
    if (state.wanted) {
      const index = Math.round((at(state.wanted) - at(answer.start)) / DAY);
      if (index >= 0 && index < answer.days) state.current = index;
      state.wanted = null;
    }
    show(Math.min(state.current, answer.days - 1));
  } catch (error) {
    if (turn !== state.asking) return;
    fail(error);
  } finally {
    if (turn === state.asking) status.textContent = "";
  }
}

function fail(error) {
  failure.hidden = false;
  failure.textContent = error instanceof SearchError ? error.message : texts.transport.serviceFailed;
}

/** Put day `index` on the map, the panel and the timeline. */
function show(index) {
  const season = state.season;
  if (!season) return;
  state.current = Math.max(0, Math.min(index, season.days - 1));
  draw();
  panel();
  relink();
  keepDay();
  drawTimeline();
}

function dateOf(index) {
  return iso(at(state.season.start) + index * DAY);
}

// --- the map ------------------------------------------------------------------

/**
 * As wide as the middle column, unless the map would then run past the bottom
 * of the window: Europe is nearly square, so on a computer screen the height is
 * what limits it. With the three columns the map has the whole height; stacked,
 * what is left under the controls.
 */
function mapWidth() {
  const shape = projection(state.frame, 1000);
  const columns = window.matchMedia("(min-width: 1000px)").matches;
  const top = columns
    ? stage.getBoundingClientRect().top - document.documentElement.getBoundingClientRect().top
    : stage.getBoundingClientRect().top + window.scrollY;
  const room = window.innerHeight - top - 16;
  const width = Math.max(280, Math.min(mapMain.clientWidth, (room * 1000) / shape.height));
  mapMain.style.setProperty("--map-width", `${Math.floor(width)}px`);
  return Math.floor(width);
}

function redraw() {
  if (!state.season || stage.hidden) return;
  draw();
  drawTimeline();
}

/**
 * A point marked on the map: a light ring on a dark one, legible on every
 * colour, the same size at any zoom.
 */
function mark(context, view, z, point) {
  const [x, y] = view.project(point.longitude, point.latitude);
  context.save();
  for (const [width, colour] of [[4.5, "rgba(11, 28, 48, 0.85)"], [2, "#faf7f0"]]) {
    context.lineWidth = width / z.scale;
    context.strokeStyle = colour;
    context.beginPath();
    context.arc(x, y, 6 / z.scale, 0, 2 * Math.PI);
    context.stroke();
  }
  context.restore();
}

/**
 * The cells of the current day, one path per band, in the coordinates of the
 * map drawn whole. In this projection a cell is a small quadrilateral, not a
 * pixel: each is drawn from its four projected corners. Kept until the day,
 * the season or the width changes: zooming and panning redraw it many times.
 */
function cellPaths(view) {
  const kept = state.image;
  if (
    kept &&
    kept.season === state.season &&
    kept.current === state.current &&
    kept.width === view.width
  ) {
    return kept;
  }
  const values = day(state.season.values, state.season.cells, state.current);
  const g = state.geometry;
  const half = g.step / 2;
  const paths = state.spec.colors.map(() => new Path2D());
  const hottest = [];
  for (let k = 0; k < values.length; k += 1) {
    if (values[k] === FILL) continue;
    const b = band(values[k] / 10, state.edges);
    if (state.spec.hatchTop && b === state.edges.length) hottest.push(k);
    const lon = g.longitude(k);
    const lat = g.latitude(k);
    const path = paths[b];
    const corners = [
      view.project(lon - half, lat + half),
      view.project(lon + half, lat + half),
      view.project(lon + half, lat - half),
      view.project(lon - half, lat - half),
    ];
    path.moveTo(...corners[0]);
    path.lineTo(...corners[1]);
    path.lineTo(...corners[2]);
    path.lineTo(...corners[3]);
    path.closePath();
  }
  state.image = { season: state.season, current: state.current, width: view.width, paths, hottest };
  return state.image;
}

/** Meridians and parallels every 10°, faint, under the cells: seen on the sea. */
function graticule(context, view, scale) {
  const box = state.box;
  context.save();
  context.strokeStyle = "rgba(236, 231, 221, 0.12)";
  context.lineWidth = 0.6 / scale;
  context.beginPath();
  for (let lon = Math.ceil(box.west / 10) * 10; lon <= box.east; lon += 10) {
    for (let lat = box.south; lat <= box.north; lat += 1) {
      const [x, y] = view.project(lon, lat);
      if (lat === box.south) context.moveTo(x, y);
      else context.lineTo(x, y);
    }
  }
  for (let lat = Math.ceil(box.south / 10) * 10; lat <= box.north; lat += 10) {
    for (let lon = box.west; lon <= box.east; lon += 1) {
      const [x, y] = view.project(lon, lat);
      if (lon === box.west) context.moveTo(x, y);
      else context.lineTo(x, y);
    }
  }
  context.stroke();
  context.restore();
}

function draw() {
  const season = state.season;
  if (!season || stage.hidden) return;
  const view = projection(state.frame, mapWidth());
  const ratio = window.devicePixelRatio || 1;
  mapCanvas.width = Math.round(view.width * ratio);
  mapCanvas.height = Math.round(view.height * ratio);
  mapCanvas.style.height = `${view.height}px`;
  const context = mapCanvas.getContext("2d");
  context.setTransform(ratio, 0, 0, ratio, 0, 0);
  context.clearRect(0, 0, view.width, view.height);

  // The zoom: everything below is drawn on the map whole, scaled and moved here.
  const z = state.zoom;
  context.setTransform(
    ratio * z.scale, 0, 0, ratio * z.scale,
    ratio * z.x * view.width, ratio * z.y * view.height,
  );

  const g = state.geometry;
  graticule(context, view, z.scale);
  const { paths, hottest } = cellPaths(view);
  // Filled, then stroked in their own colour: neighbouring cells meet without
  // the hairline gap antialiasing would leave between them.
  context.lineWidth = 0.5 / z.scale;
  paths.forEach((path, b) => {
    context.fillStyle = state.spec.colors[b];
    context.strokeStyle = state.spec.colors[b];
    context.fill(path);
    context.stroke(path);
  });

  // 40 °C and above: the darkest colour, hatched, so that it never reads as a shadow.
  // Line widths are divided by the zoom: a stroke stays a hairline at any scale.
  if (hottest.length) {
    context.save();
    context.strokeStyle = "rgba(236, 231, 221, 0.55)";
    context.lineWidth = 0.8 / z.scale;
    for (const k of hottest) {
      const [cx, cy] = view.project(g.longitude(k) - g.step / 2, g.latitude(k) + g.step / 2);
      const [dx, dy] = view.project(g.longitude(k) + g.step / 2, g.latitude(k) - g.step / 2);
      context.beginPath();
      context.moveTo(cx, dy);
      context.lineTo(dx, cy);
      context.stroke();
    }
    context.restore();
  }

  context.strokeStyle = "rgba(236, 231, 221, 0.5)";
  context.lineWidth = 0.6 / Math.sqrt(z.scale);
  context.lineJoin = "round";
  context.beginPath();
  for (const ring of state.rings) {
    ring.forEach(([lon, lat], i) => {
      const [x, y] = view.project(lon, lat);
      if (i === 0) context.moveTo(x, y);
      else context.lineTo(x, y);
    });
    context.closePath();
  }
  context.stroke();

  if (isobarsField.checked && state.pressure) drawIsobars(context, view, z);

  state.view = view;
  if (state.place) mark(context, view, z, state.place);
  if (state.pick) mark(context, view, z, state.pick);
  placePick();
  zoomOut.disabled = z.scale <= 1;
  zoomWhole.disabled = z.scale <= 1;
  zoomIn.disabled = z.scale >= MAX_ZOOM;
  mapCanvas.classList.toggle("zoomed", z.scale > 1);
  if (state.hover) tooltip(state.hover);
}

/**
 * The isobars of the current day: for each level, its segments in the
 * coordinates of the map drawn whole, and the middle of every segment as a
 * candidate for its label. Kept until the day or the width changes.
 */
function isobarLines(view) {
  const kept = state.lines;
  if (kept && kept.current === state.current && kept.width === view.width) return kept;
  const p = state.pressure;
  const field = p.values.subarray(state.current * p.rows * p.cols, (state.current + 1) * p.rows * p.cols);
  const at = (r, c) => view.project(p.west + c * p.step, p.north - r * p.step);
  const lines = levels(field).map((level) => {
    const path = new Path2D();
    const middles = [];
    for (const [r0, c0, r1, c1] of contour(field, p.rows, p.cols, level * 10)) {
      const a = at(r0, c0);
      const b = at(r1, c1);
      path.moveTo(...a);
      path.lineTo(...b);
      middles.push([(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]);
    }
    return { level, path, middles };
  });
  state.lines = { current: state.current, width: view.width, lines };
  return state.lines;
}

/**
 * The isobars over the cells: a light line on a dark one, legible over the
 * bright colours and over the sea alike; their values written where there is
 * room, kept 140 pixels apart on screen.
 */
function drawIsobars(context, view, z) {
  const { lines } = isobarLines(view);
  context.save();
  context.lineJoin = "round";
  context.lineCap = "round";
  for (const [width, colour] of [[2.4, "rgba(11, 28, 48, 0.55)"], [1, "rgba(250, 247, 240, 0.9)"]]) {
    context.lineWidth = width / z.scale;
    context.strokeStyle = colour;
    for (const { path } of lines) context.stroke(path);
  }
  const size = 11 / z.scale;
  context.font = `500 ${size}px system-ui, sans-serif`;
  context.textAlign = "center";
  context.textBaseline = "middle";
  context.lineWidth = 3 / z.scale;
  context.strokeStyle = "rgba(11, 28, 48, 0.8)";
  context.fillStyle = "#faf7f0";
  const taken = [];
  for (const { level, middles } of lines) {
    const candidates = middles.filter((_, k) => k % 4 === 0);
    for (const [x, y] of labelSpots(candidates, 140 / z.scale, taken)) {
      taken.push([x, y]);
      context.strokeText(String(level), x, y);
      context.fillText(String(level), x, y);
    }
  }
  context.restore();
}

/** Zoom by `factor` about (cx, cy) of the frame, the centre by default. */
function zoomBy(factor, cx = state.view.width / 2, cy = state.view.height / 2) {
  state.zoom = zoomAt(state.zoom, factor, cx, cy, state.view.width, state.view.height);
  draw();
}

function wireMap() {
  const pointers = new Map();
  let pinch = null;
  const at = (event) => {
    const box = mapCanvas.getBoundingClientRect();
    return [event.clientX - box.left, event.clientY - box.top];
  };

  mapCanvas.addEventListener("wheel", (event) => {
    if (!state.view) return;
    event.preventDefault();
    const [x, y] = at(event);
    zoomBy(Math.exp(-event.deltaY * 0.002), x, y);
  }, { passive: false });

  mapCanvas.addEventListener("dblclick", (event) => {
    if (!state.view) return;
    const [x, y] = at(event);
    zoomBy(2, x, y);
  });

  // A press that barely moved, one finger only, is a click: the cell is picked.
  let pressed = null;
  mapCanvas.addEventListener("pointerdown", (event) => {
    pointers.set(event.pointerId, at(event));
    mapCanvas.setPointerCapture(event.pointerId);
    pressed = pointers.size === 1 ? at(event) : null;
  });

  mapCanvas.addEventListener("pointermove", (event) => {
    const here = at(event);
    const before = pointers.get(event.pointerId);
    if (!before) {
      // Hovering, nothing pressed: the value under the pointer.
      state.hover = here;
      tooltip(here);
      return;
    }
    pointers.set(event.pointerId, here);
    tip.hidden = true;
    state.hover = null;
    if (pointers.size === 2) {
      // Two fingers: the distance between them is the zoom, their middle the centre.
      const [a, b] = [...pointers.values()];
      const distance = Math.hypot(a[0] - b[0], a[1] - b[1]);
      const middle = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
      if (pinch) zoomBy(distance / pinch, ...middle);
      pinch = distance;
    } else if (pointers.size === 1 && state.zoom.scale > 1) {
      state.zoom = pan(state.zoom, here[0] - before[0], here[1] - before[1], state.view.width, state.view.height);
      draw();
    }
  });

  const release = (event) => {
    const was = pointers.get(event.pointerId);
    pointers.delete(event.pointerId);
    if (pointers.size < 2) pinch = null;
    if (event.type === "pointerup" && pressed && was && state.view) {
      const [x, y] = at(event);
      if (Math.hypot(x - pressed[0], y - pressed[1]) < CLICK) pick(x, y);
    }
    pressed = null;
  };
  mapCanvas.addEventListener("pointerup", release);
  mapCanvas.addEventListener("pointercancel", release);
  mapCanvas.addEventListener("pointerleave", () => {
    state.hover = null;
    tip.hidden = true;
  });

  pickClose.addEventListener("click", unpick);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && state.pick) unpick();
  });

  zoomIn.addEventListener("click", () => zoomBy(2));
  zoomOut.addEventListener("click", () => zoomBy(0.5));
  zoomWhole.addEventListener("click", () => {
    state.zoom = WHOLE;
    draw();
  });
}

/** The longitude and latitude under a point of the canvas, zoom undone. */
function pointAt(x, y) {
  return state.view.unproject(...unzoom(state.zoom, x, y, state.view.width, state.view.height));
}

/** Where a longitude and a latitude are on the canvas, zoomed. */
function screenOf(lon, lat) {
  const [x, y] = state.view.project(lon, lat);
  const z = state.zoom;
  return [x * z.scale + z.x * state.view.width, y * z.scale + z.y * state.view.height];
}

/** The value under the pointer, or nothing over the sea. */
function tooltip([x, y]) {
  if (!state.view || !state.season) return;
  const g = state.geometry;
  const [lon, lat] = pointAt(x, y);
  const k = cellAt(lon, lat);
  const value = k === undefined ? FILL : day(state.season.values, state.season.cells, state.current)[k];
  // The cell picked already has its card: no second label over it.
  if (value === FILL || k === state.pick?.k) {
    tip.hidden = true;
    return;
  }
  tip.replaceChildren(
    el("strong", { className: "maps-figure" }, measureNodes(value / 10)),
    el("span", { text: where(g.latitude(k), g.longitude(k)) }),
  );
  tip.style.left = `${x}px`;
  tip.style.top = `${y}px`;
  tip.hidden = false;
}

// --- the way to the results ---------------------------------------------------

/** The value of the day on screen at cell `k`, with its unit, or "". */
/** The same, as nodes for the page (nothing over the sea). */
function nodesAt(k) {
  const text = valueAt(k);
  if (!text) return [];
  return measureNodes(day(state.season.values, state.season.cells, state.current)[k] / 10);
}

function valueAt(k) {
  if (k === undefined || !state.season) return "";
  const value = day(state.season.values, state.season.cells, state.current)[k];
  return value === FILL ? "" : measure(value / 10);
}

/** The place the visitor came from: its label and the link back to its results. */
function linkHere() {
  const place = state.place;
  here.hidden = !place;
  if (place) {
    hereLabel.textContent = texts.maps.here(place.name);
    hereLink.textContent = texts.maps.hereLink(place.name);
  }
  relink();
}

/** The season and year chosen, and the day on screen when it is of them. */
function shownPeriod() {
  return {
    season: seasonField.value,
    year: Number(yearField.value),
    day: state.season ? dateOf(state.current) : null,
  };
}

/** Both links to the results, on the season chosen and the day on screen, and the bar. */
function relink() {
  const place = state.place;
  if (place) hereLink.href = resultsHref({ ...place, place: place.name, ...shownPeriod() });
  if (state.pick) linkPick();
  fillNav({
    current: "map",
    season: seasonField.value,
    year: Number(yearField.value),
    place: place?.name ?? null,
    // The tab leads to the top of the results; the link of the panel, to the day.
    placeHref: place ? resultsHref({ ...place, place: place.name, ...shownPeriod(), day: null }) : null,
    mapHref: `${window.location.pathname}${window.location.search}`,
  });
}

/** The day on screen in the URL, when the player is stopped. */
function keepDay() {
  if (!state.season || state.playing) return;
  const url = new URL(window.location.href);
  url.searchParams.set("jour", dateOf(state.current));
  history.replaceState(null, "", url);
}

/**
 * Pick the land cell under (x, y): the card opens at once with its value and
 * coordinates; the name of the town near it follows from the server. Over the
 * sea, nothing.
 */
async function pick(x, y) {
  const [lon, lat] = pointAt(x, y);
  const k = cellAt(lon, lat);
  if (k === undefined || valueAt(k) === "") {
    unpick();
    return;
  }
  const turn = (state.picking += 1);
  const coordinates = where(lat, lon);
  state.pick = { latitude: lat, longitude: lon, k, label: coordinates, turn };
  tip.hidden = true;
  pickValue.replaceChildren(...nodesAt(k));
  pickName.textContent = texts.maps.pick.searching;
  pickWhere.textContent = coordinates;
  linkPick();
  pickCard.hidden = false;
  draw();
  try {
    const near = await nearestPlace(Math.round(lat * 1e4) / 1e4, Math.round(lon * 1e4) / 1e4);
    if (turn !== state.picking) return;
    if (near.name) {
      const country = near.country ? COUNTRIES.of(near.country) : "";
      // Within 3 km the point is the town; farther, it is near it.
      pickName.textContent = near.distance_km <= 3
        ? texts.maps.pick.at(near.name, country)
        : texts.maps.pick.near(near.name, country);
      state.pick.label = near.name;
    } else {
      pickName.textContent = "";
    }
  } catch {
    if (turn === state.picking) pickName.textContent = "";
  }
  if (turn === state.picking) linkPick();
}

function unpick() {
  state.picking += 1;
  state.pick = null;
  pickCard.hidden = true;
  if (state.view) draw();
}

/** The link of the card: the results of the point, on the season shown. */
function linkPick() {
  const p = state.pick;
  pickLink.href = resultsHref({
    place: p.label,
    latitude: p.latitude,
    longitude: p.longitude,
    ...shownPeriod(),
  });
}

/** The card over its point; hidden when the point is out of the frame. */
function placePick() {
  const p = state.pick;
  if (!p || !state.view) return;
  const [x, y] = screenOf(p.longitude, p.latitude);
  const out = x < 0 || y < 0 || x > state.view.width || y > state.view.height;
  pickCard.hidden = out;
  pickCard.style.left = `${x}px`;
  pickCard.style.top = `${y}px`;
}

// --- the panel ----------------------------------------------------------------

function panel() {
  const s = state.summaries[state.current];
  dateLine.textContent = present.fullDate(dateOf(state.current));
  dayLine.textContent = texts.maps.dayOf(state.current + 1, state.season.days);
  hereValue.replaceChildren(...nodesAt(state.place?.k));
  if (state.pick) pickValue.replaceChildren(...nodesAt(state.pick.k));
  const most = Math.max(...s.counts);
  const rows = [...bandList.children].reverse();
  s.counts.forEach((count, b) => {
    const share = s.cells ? count / s.cells : 0;
    rows[b].querySelector(".maps-bar").style.width = `${most ? (count / most) * 100 : 0}%`;
    rows[b].querySelector(".maps-share").textContent = count ? PERCENT.format(share) : "";
    rows[b].classList.toggle("empty", count === 0);
  });
}

// --- the timeline and the player ----------------------------------------------

function drawTimeline() {
  const width = timeline.clientWidth;
  const height = 56;
  const ratio = window.devicePixelRatio || 1;
  timeline.width = Math.round(width * ratio);
  timeline.height = Math.round(height * ratio);
  timeline.style.height = `${height}px`;
  const context = timeline.getContext("2d");
  context.setTransform(ratio, 0, 0, ratio, 0, 0);
  context.clearRect(0, 0, width, height);

  // Each day's bar: the median of the cells, or their mean for rain (whose
  // median is nought most summer days). Temperatures are framed on their
  // range, rain and cloud cover from zero.
  const n = state.season.days;
  const column = width / n;
  const stat = (s) => (state.spec.timeline === "mean" ? s.mean : s.median);
  const values = state.summaries.map((s) => stat(s) ?? 0);
  const temperature = state.spec.unit === "°C";
  const low = temperature ? Math.min(...values) - 2 : 0;
  const high = temperature ? Math.max(...values) + 1 : Math.max(...values, 1) * 1.05;
  state.summaries.forEach((s, k) => {
    const value = stat(s);
    if (value === null) return;
    const h = Math.max(1, ((value - low) / (high - low)) * (height - 8));
    context.fillStyle = state.spec.colors[band(value, state.edges)];
    context.fillRect(k * column + 0.5, height - h, Math.max(1, column - 1), h);
  });
  context.fillStyle = "#ece7dd";
  context.fillRect(state.current * column + column / 2 - 1, 0, 2, height);

  timeline.setAttribute("aria-valuemin", "1");
  timeline.setAttribute("aria-valuemax", String(n));
  timeline.setAttribute("aria-valuenow", String(state.current + 1));
  timeline.setAttribute("aria-valuetext", present.fullDate(dateOf(state.current)));
}

function play(on) {
  clearInterval(state.playing);
  state.playing = null;
  if (on) {
    state.playing = setInterval(() => {
      show(state.current + 1 >= state.season.days ? 0 : state.current + 1);
    }, 1000 / Number(speedField.value));
  }
  if (!on) keepDay();
  // The sign and the name say what a press will do: pause while it plays.
  const name = on ? texts.maps.pause : texts.maps.play;
  playButton.classList.toggle("is-playing", Boolean(on));
  playButton.setAttribute("aria-label", name);
  playButton.title = name;
}

function wirePlayer() {
  playButton.addEventListener("click", () => play(!state.playing));
  prevButton.addEventListener("click", () => {
    play(false);
    show(state.current - 1);
  });
  nextButton.addEventListener("click", () => {
    play(false);
    show(state.current + 1);
  });
  let dragging = false;
  const seek = (event) => {
    const box = timeline.getBoundingClientRect();
    show(Math.floor(((event.clientX - box.left) / box.width) * state.season.days));
  };
  timeline.addEventListener("pointerdown", (event) => {
    dragging = true;
    timeline.setPointerCapture(event.pointerId);
    play(false);
    seek(event);
  });
  timeline.addEventListener("pointermove", (event) => {
    if (dragging) seek(event);
  });
  timeline.addEventListener("pointerup", () => {
    dragging = false;
  });
  timeline.addEventListener("keydown", (event) => {
    const moves = { ArrowLeft: -1, ArrowRight: 1, PageDown: -7, PageUp: 7 };
    if (event.key in moves) show(state.current + moves[event.key]);
    else if (event.key === "Home") show(0);
    else if (event.key === "End") show(state.season.days - 1);
    else return;
    play(false);
    event.preventDefault();
  });
}
