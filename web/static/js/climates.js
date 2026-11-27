/**
 * The page /climats: the Köppen-Geiger classes of Europe in 1991-2020 and in
 * 2071-2100, one map and a switch between the two, zoomed and moved as the map
 * page is (mapview.js). Opened on the whole of Europe, on 2071-2100.
 *
 * Fetched once: the grid and the two grey images of the classes (static files,
 * src/store/koppen.py), the country outlines, the config (the scenario).
 * Each period is painted once into an image of the map drawn whole
 * (koppenmap.js, `paint`); the zoom only scales it, without smoothing once
 * the cells are larger than its pixels.
 *
 * A place may come in the URL (lieu, lat, lon and the rest of the query of the
 * results page): it is marked, the panel gives its two classes at its cell,
 * and the link back opens its results with the same query.
 */

import { applyTexts, el } from "./dom.js";
import { wireHints } from "./hint.js";
import { loadConfig, outlines } from "./fetch.js";
import { texts } from "./i18n.js";
import { MAX_ZOOM, WHOLE, boxFrame, pan, projection, unzoom, zoomAt } from "./mapview.js";
import { classAt, COLORS, paint, present } from "./koppenmap.js";
import { fillNav } from "./nav.js";

/** The width of the images painted, in pixels of the map drawn whole. */
const BASE = 2400;
const PERIODS = ["1991-2020", "2071-2100"];

const stage = document.getElementById("climates-stage");
const mapMain = document.getElementById("maps-main");
const mapCanvas = document.getElementById("map");
const tip = document.getElementById("maps-tip");
const status = document.getElementById("maps-status");
const failure = document.getElementById("climates-failure");
const origin = document.getElementById("climates-origin");
const legendList = document.getElementById("climates-legend");
const switches = [...document.querySelectorAll(".climates-switch .toggle")];
const zoomIn = document.getElementById("maps-zoom-in");
const zoomOut = document.getElementById("maps-zoom-out");
const zoomWhole = document.getElementById("maps-zoom-whole");
const here = document.getElementById("climates-here");
const hereLabel = document.getElementById("climates-here-label");
const herePast = document.getElementById("climates-here-past");
const hereFuture = document.getElementById("climates-here-future");
const hereLink = document.getElementById("climates-here-link");

applyTexts();
wireHints();

const state = {
  meta: null,
  grids: {}, // period: Uint8Array of the classes
  images: {}, // period: canvas of the map drawn whole, BASE wide
  frame: null,
  rings: [],
  period: "2071-2100",
  zoom: WHOLE,
  view: null,
  place: null,
  scenario: "",
};

boot();

async function boot() {
  status.textContent = texts.climates.loading;
  try {
    const [meta, shapes, config] = await Promise.all([
      fetch("/static/geo/koppen.json").then((r) => (r.ok ? r.json() : Promise.reject(new Error(r.status)))),
      outlines(),
      loadConfig().catch(() => null),
    ]);
    state.meta = meta;
    state.rings = shapes.rings;
    state.frame = boxFrame(shapes.box);
    state.scenario = config?.simulation?.scenario ?? "";
    for (const period of meta.periods) state.grids[period.label] = await classesOf(period.file);
  } catch (error) {
    status.textContent = "";
    failure.hidden = false;
    failure.textContent = texts.climates.failed;
    return;
  }
  state.place = placeOf(new URLSearchParams(window.location.search));
  fillPlace();
  fillLegend();
  for (const button of switches) {
    button.addEventListener("click", () => choose(button.dataset.period));
  }
  status.textContent = "";
  stage.hidden = false;
  choose(state.period);
  wireMap();
  new ResizeObserver(draw).observe(mapMain);
  window.addEventListener("resize", draw);
  // The other period painted while the visitor looks at the first.
  setTimeout(() => PERIODS.forEach(image), 0);
}

/** The classes of a grey image: one byte per cell, read without any colour correction. */
async function classesOf(file) {
  const response = await fetch(`/static/geo/${file}`);
  if (!response.ok) throw new Error(String(response.status));
  const bitmap = await createImageBitmap(await response.blob(), {
    colorSpaceConversion: "none",
    premultiplyAlpha: "none",
  });
  const canvas = document.createElement("canvas");
  canvas.width = bitmap.width;
  canvas.height = bitmap.height;
  const context = canvas.getContext("2d", { willReadFrequently: true });
  context.drawImage(bitmap, 0, 0);
  const rgba = context.getImageData(0, 0, bitmap.width, bitmap.height).data;
  const classes = new Uint8Array(bitmap.width * bitmap.height);
  for (let k = 0; k < classes.length; k += 1) classes[k] = rgba[k * 4];
  return classes;
}

/** The map of a period drawn whole, painted once. */
function image(period) {
  if (state.images[period]) return state.images[period];
  const whole = projection(state.frame, BASE);
  const height = Math.round(whole.height);
  const canvas = document.createElement("canvas");
  canvas.width = BASE;
  canvas.height = height;
  const context = canvas.getContext("2d");
  const data = context.createImageData(BASE, height);
  data.data.set(paint(state.meta, state.grids[period], BASE, height, whole.unproject));
  context.putImageData(data, 0, 0);
  state.images[period] = canvas;
  return canvas;
}

function choose(period) {
  state.period = period;
  for (const button of switches) button.setAttribute("aria-pressed", String(button.dataset.period === period));
  const simulated = state.meta.periods.find((p) => p.label === period)?.origin === "simulated";
  origin.textContent = simulated ? texts.climates.simulated(state.scenario) : texts.climates.observed;
  fillLegend();
  draw();
}

/** The place of the URL, or null; the query is kept for the way back. */
function placeOf(query) {
  const name = query.get("lieu");
  const latitude = Number(query.get("lat"));
  const longitude = Number(query.get("lon"));
  if (!name || !query.has("lat") || !query.has("lon")) return null;
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) return null;
  return { name, latitude, longitude, back: `/resultats?${query}` };
}

/** The two classes of a point, as the panel and the tooltip write them. */
function described(lon, lat) {
  return PERIODS.map((period) => {
    const code = classAt(state.meta, state.grids[period], lon, lat);
    return { period, code, line: code ? texts.climates.classLine(period, code, texts.climate.koppenNames[code]) : "" };
  });
}

function fillPlace() {
  const place = state.place;
  here.hidden = !place;
  if (!place) {
    fillNav({ current: null });
    return;
  }
  const [past, future] = described(place.longitude, place.latitude);
  hereLabel.textContent = place.name;
  herePast.textContent = past.line || texts.climates.none(past.period);
  hereFuture.textContent = future.line || texts.climates.none(future.period);
  hereLink.href = place.back;
  hereLink.textContent = texts.climates.back(place.name);
  fillNav({ current: null, place: place.name, placeHref: place.back });
}

/** The classes of either period, those absent from the one shown softened. */
function fillLegend() {
  const shownHere = new Set(present(state.meta, state.grids[state.period]));
  legendList.replaceChildren(
    ...present(state.meta, ...Object.values(state.grids)).map((code) =>
      el("li", { className: shownHere.has(code) ? "" : "empty" }, [
        el("span", { className: "maps-swatch", attrs: { style: `background: ${COLORS[code]}`, "aria-hidden": "true" } }),
        el("span", { className: "climates-code", text: code }),
        el("span", { text: texts.climate.koppenNames[code] ?? "" }),
      ]),
    ),
  );
}

/** As wide as the column allows, as tall as the window leaves (the map page's rule). */
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

function draw() {
  if (!state.meta || stage.hidden) return;
  const view = projection(state.frame, mapWidth());
  const ratio = window.devicePixelRatio || 1;
  mapCanvas.width = Math.round(view.width * ratio);
  mapCanvas.height = Math.round(view.height * ratio);
  mapCanvas.style.height = `${view.height}px`;
  const context = mapCanvas.getContext("2d");
  context.setTransform(ratio, 0, 0, ratio, 0, 0);
  context.clearRect(0, 0, view.width, view.height);
  const z = state.zoom;
  context.setTransform(ratio * z.scale, 0, 0, ratio * z.scale, ratio * z.x * view.width, ratio * z.y * view.height);

  // Smoothed while the image is shrunk, sharp once its pixels are enlarged:
  // a cell is then a block of colour, as on the map page.
  context.imageSmoothingEnabled = view.width * z.scale * ratio < BASE;
  context.drawImage(image(state.period), 0, 0, view.width, view.height);

  context.strokeStyle = "rgba(20, 20, 20, 0.55)";
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
  if (state.place) mark(context, view, z, state.place);
  zoomOut.disabled = z.scale <= 1;
  zoomWhole.disabled = z.scale <= 1;
  zoomIn.disabled = z.scale >= MAX_ZOOM;
  mapCanvas.classList.toggle("zoomed", z.scale > 1);
}

/** The place, a light ring on a dark one, the same size at any zoom (the map page's mark). */
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

function zoomBy(factor, cx = state.view.width / 2, cy = state.view.height / 2) {
  state.zoom = zoomAt(state.zoom, factor, cx, cy, state.view.width, state.view.height);
  draw();
}

/** The two classes under the pointer, or nothing over the sea. */
function tooltip([x, y]) {
  if (!state.view) return;
  const [lon, lat] = state.view.unproject(...unzoom(state.zoom, x, y, state.view.width, state.view.height));
  const lines = described(lon, lat);
  if (!lines.some((line) => line.code)) {
    tip.hidden = true;
    return;
  }
  tip.replaceChildren(
    ...lines.map((line) =>
      el(line.period === state.period ? "strong" : "span", {
        className: "climates-tip-line",
        text: line.line || texts.climates.none(line.period),
      }),
    ),
  );
  tip.style.left = `${x}px`;
  tip.style.top = `${y}px`;
  tip.hidden = false;
}

/** Wheel, double click, drag and pinch, as on the map page; no cell is picked here. */
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
    zoomBy(Math.exp(-event.deltaY * 0.002), ...at(event));
  }, { passive: false });
  mapCanvas.addEventListener("dblclick", (event) => {
    if (state.view) zoomBy(2, ...at(event));
  });
  mapCanvas.addEventListener("pointerdown", (event) => {
    pointers.set(event.pointerId, at(event));
    mapCanvas.setPointerCapture(event.pointerId);
    // A touch shows the classes under the finger, as hovering does.
    if (event.pointerType !== "mouse") tooltip(at(event));
  });
  mapCanvas.addEventListener("pointermove", (event) => {
    const now = at(event);
    const before = pointers.get(event.pointerId);
    if (!before) {
      tooltip(now);
      return;
    }
    pointers.set(event.pointerId, now);
    if (pointers.size === 2) {
      tip.hidden = true;
      const [a, b] = [...pointers.values()];
      const distance = Math.hypot(a[0] - b[0], a[1] - b[1]);
      if (pinch) zoomBy(distance / pinch, (a[0] + b[0]) / 2, (a[1] + b[1]) / 2);
      pinch = distance;
    } else if (pointers.size === 1 && state.zoom.scale > 1) {
      tip.hidden = true;
      state.zoom = pan(state.zoom, now[0] - before[0], now[1] - before[1], state.view.width, state.view.height);
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
    tip.hidden = true;
  });
  zoomIn.addEventListener("click", () => zoomBy(2));
  zoomOut.addEventListener("click", () => zoomBy(0.5));
  zoomWhole.addEventListener("click", () => {
    state.zoom = WHOLE;
    draw();
  });
}
