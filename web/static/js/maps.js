/**
 * The map page: one variable over Europe, a season day after day.
 *
 * Four things are fetched: the config (periods, band edges), the land cells and
 * the variables served (once), the country outlines (a static file), and the
 * season itself, as integers. How each variable is drawn is in mapview.js
 * (VARIABLES). Everything drawn is read from those; the arithmetic is in
 * mapview.js, this file is the wiring: the period chosen, the map, the panel,
 * the timeline and the player.
 */

import { DAY, at, iso } from "./calendar.js";
import { applyTexts, el } from "./dom.js";
import { loadConfig, mapCells, mapDays, outlines, SearchError } from "./fetch.js";
import { texts } from "./i18n.js";
import {
  FILL,
  MAX_ZOOM,
  WHOLE,
  band,
  day,
  frame,
  grid,
  pan,
  projection,
  summary,
  unzoom,
  VARIABLES,
  zoomAt,
} from "./mapview.js";
import * as present from "./present.js";
import { rangeOf, yearsFor } from "./season.js";

/** Europe is northern: the seasons are read at this latitude. */
const LATITUDE = 50;
const SEASONS = ["spring", "summer", "autumn", "winter"];
const DEFAULT = { variable: "tasmax", season: "summer", year: 2100 };
const SPEEDS = [1, 3, 8];

const title = document.getElementById("maps-title");
const variableField = document.getElementById("maps-variable");
const seasonField = document.getElementById("maps-season");
const yearField = document.getElementById("maps-year");
const warning = document.getElementById("maps-warning");
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
const firstLabel = document.getElementById("maps-first-label");
const firstValue = document.getElementById("maps-first");
const firstWhere = document.getElementById("maps-first-where");
const secondLabel = document.getElementById("maps-second-label");
const secondValue = document.getElementById("maps-second");
const cellsLine = document.getElementById("maps-cells");
const bandList = document.getElementById("maps-bands");
const playButton = document.getElementById("maps-play");
const prevButton = document.getElementById("maps-prev");
const nextButton = document.getElementById("maps-next");
const speedField = document.getElementById("maps-speed");
const timeline = document.getElementById("maps-timeline");

applyTexts();

const ONE_DECIMAL = new Intl.NumberFormat("fr-FR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const WHOLE_NUMBER = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 });
const PERCENT = new Intl.NumberFormat("fr-FR", { style: "percent", maximumFractionDigits: 0 });
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
  summaries: [],
  current: 0,
  playing: null,
  hover: null,
  zoom: WHOLE,
  image: null, // { values, canvas, hottest }: the cells of the day on screen
  asking: 0,
};

boot();

async function boot() {
  try {
    const [config, cells, shapes] = await Promise.all([loadConfig(), mapCells(), outlines()]);
    state.config = config;
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
  return { variable, season, year };
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
  history.replaceState(
    null,
    "",
    `?${new URLSearchParams({ grandeur: variable, saison: season, annee: String(year) })}`,
  );
  title.textContent = texts.maps.title(texts.maps.variables[variable], texts.season[season], year);
  document.title = `${title.textContent} · ${texts.maps.pageTitle}`;
  failure.hidden = true;
  status.textContent = texts.maps.loading;

  try {
    const answer = await mapDays(variable, range.start, range.end);
    if (turn !== state.asking) return;
    state.season = answer;
    state.summaries = Array.from({ length: answer.days }, (_, k) =>
      summary(day(answer.values, answer.cells, k), state.edges),
    );
    warning.hidden = answer.origin !== "simulated";
    stage.hidden = false;
    player.hidden = false;
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

  state.view = view;
  zoomOut.disabled = z.scale <= 1;
  zoomWhole.disabled = z.scale <= 1;
  zoomIn.disabled = z.scale >= MAX_ZOOM;
  mapCanvas.classList.toggle("zoomed", z.scale > 1);
  if (state.hover) tooltip(state.hover);
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

  mapCanvas.addEventListener("pointerdown", (event) => {
    pointers.set(event.pointerId, at(event));
    mapCanvas.setPointerCapture(event.pointerId);
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
    pointers.delete(event.pointerId);
    if (pointers.size < 2) pinch = null;
  };
  mapCanvas.addEventListener("pointerup", release);
  mapCanvas.addEventListener("pointercancel", release);
  mapCanvas.addEventListener("pointerleave", () => {
    state.hover = null;
    tip.hidden = true;
  });

  zoomIn.addEventListener("click", () => zoomBy(2));
  zoomOut.addEventListener("click", () => zoomBy(0.5));
  zoomWhole.addEventListener("click", () => {
    state.zoom = WHOLE;
    draw();
  });
}

/** The value under the pointer, or nothing over the sea. */
function tooltip([x, y]) {
  if (!state.view || !state.season) return;
  const g = state.geometry;
  const [lon, lat] = state.view.unproject(
    ...unzoom(state.zoom, x, y, state.view.width, state.view.height),
  );
  const row = Math.floor((g.north - lat) / g.step);
  const col = Math.floor((lon - g.west) / g.step);
  const k = row >= 0 && col >= 0 && col < g.cols ? g.index.get(row * g.cols + col) : undefined;
  const value = k === undefined ? FILL : day(state.season.values, state.season.cells, state.current)[k];
  if (value === FILL) {
    tip.hidden = true;
    return;
  }
  tip.replaceChildren(
    el("strong", { text: measure(value / 10) }),
    el("span", { text: where(g.latitude(k), g.longitude(k)) }),
  );
  tip.style.left = `${x}px`;
  tip.style.top = `${y}px`;
  tip.hidden = false;
}

// --- the panel ----------------------------------------------------------------

/**
 * One figure of the panel: the highest or the lowest cell (and where), the
 * median, or the share of cells in the first band (dry, clear), as VARIABLES
 * says.
 */
function figure(kind, s) {
  const g = state.geometry;
  if (kind === "min") {
    return {
      label: texts.maps.figures.min[state.variable],
      value: s.coldest === null ? "" : measure(s.coldest),
      where: s.coldAt < 0 ? "" : where(g.latitude(s.coldAt), g.longitude(s.coldAt)),
    };
  }
  if (kind === "max") {
    return {
      label: texts.maps.figures.max[state.variable],
      value: s.hottest === null ? "" : measure(s.hottest),
      where: s.at < 0 ? "" : where(g.latitude(s.at), g.longitude(s.at)),
    };
  }
  if (kind === "share") {
    return {
      label: texts.maps.figures.share[state.variable],
      value: s.cells ? PERCENT.format(s.counts[0] / s.cells) : "",
      where: "",
    };
  }
  return { label: texts.maps.figures.median, value: s.median === null ? "" : measure(s.median), where: "" };
}

function panel() {
  const s = state.summaries[state.current];
  dateLine.textContent = present.fullDate(dateOf(state.current));
  dayLine.textContent = texts.maps.dayOf(state.current + 1, state.season.days);
  const first = figure(state.spec.first, s);
  const second = figure(state.spec.second, s);
  firstLabel.textContent = first.label;
  firstValue.textContent = first.value;
  firstWhere.textContent = first.where;
  secondLabel.textContent = second.label;
  secondValue.textContent = second.value;
  cellsLine.textContent = texts.maps.cells(s.cells);
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
  playButton.setAttribute("aria-pressed", String(Boolean(on)));
  playButton.textContent = on ? texts.maps.pause : texts.maps.play;
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
