/**
 * The climate diagram: twelve months at the place, over the 15 years around the
 * year searched, beside a reference period in grey.
 *
 * **One plot, two axes, and that is the exception this drawing exists for.**
 * The chart above refuses two scales on one plot, because where they meet is
 * arbitrary. Here it is not: the rain axis is twice the temperature axis
 * (10 °C level with 20 mm), the scale of Bagnouls and Gaussen, so the crossing
 * means something: a month whose rain bar falls short of the temperature curve
 * is a dry month, P <= 2T. Which months are dry is said by the server (`dry`);
 * this file only draws it.
 *
 * No fetching, no state: months go in, one node comes out.
 */

import { svg } from "./dom.js";
import { texts } from "./i18n.js";
import * as present from "./present.js";

export const BOX = { width: 1000, height: 380, left: 68, right: 68, top: 30, bottom: 40 };

/** Rain is drawn at half its value on the temperature axis: 20 mm level with 10 °C. */
export const RAIN_PER_DEGREE = 2;

const missing = present.isMissing;

/**
 * The temperature window, in degrees: from zero (or the coldest month, on the
 * multiple of five below) to the multiple of ten above the warmest month or the
 * wettest month's rain, whichever reaches higher. Framed on both series at
 * once, or the grey and the coloured would each be drawn on their own scale.
 */
export function window(...series) {
  const months = series.flat();
  const lows = months.map((m) => m.temperature_mean).filter((v) => !missing(v));
  const highs = [
    ...lows,
    ...months.map((m) => m.precipitation).filter((v) => !missing(v)).map((v) => v / RAIN_PER_DEGREE),
  ];
  const bottom = Math.min(0, Math.floor(Math.min(...lows, 0) / 5) * 5);
  const top = Math.max(20, Math.ceil(Math.max(...highs, 0) / 10) * 10);
  return { bottom, top };
}

/** The highest degree numbered on the left axis: the ten above the warmest month. */
export function labelTop(...series) {
  const means = series.flat().map((m) => m.temperature_mean).filter((v) => !missing(v));
  return Math.max(10, Math.ceil(Math.max(...means, 0) / 10) * 10);
}

/**
 * Every 5 °C, or every 10 when the window is tall: never more than ten lines.
 * On the multiples of the step, so that zero is always ruled.
 */
export function ticks({ bottom, top }) {
  const step = top - bottom > 50 ? 10 : 5;
  const values = [];
  // "+ 0" turns the -0 that Math.ceil(-0.5) gives into a plain 0.
  for (let value = Math.ceil(bottom / step) * step + 0; value <= top; value += step) values.push(value);
  return values;
}

/** Annual mean temperature, annual rain and the dry months, for the line under the drawing. */
export function summary(months) {
  const temperatures = months.map((m) => m.temperature_mean).filter((v) => !missing(v));
  const rains = months.map((m) => m.precipitation).filter((v) => !missing(v));
  return {
    temperature: temperatures.length === 12 ? temperatures.reduce((a, b) => a + b) / 12 : null,
    precipitation: rains.length === 12 ? rains.reduce((a, b) => a + b) : null,
    dry: months.filter((m) => m.dry).map((m) => m.month),
  };
}

export function diagram(answer, box = BOX) {
  const span = window(answer.months, answer.reference_months);
  const plot = { from: box.left, to: box.width - box.right, top: box.top, bottom: box.height - box.bottom };
  const column = (plot.to - plot.from) / 12;
  const x = (index) => plot.from + column * index;
  const middle = (index) => x(index) + column / 2;
  const y = (degrees) =>
    plot.top + ((span.top - degrees) / (span.top - span.bottom)) * (plot.bottom - plot.top);
  const base = y(0);

  const dry = answer.months.flatMap((m, index) =>
    m.dry
      ? [svg("rect", {
          className: "climate-dry",
          attrs: { x: round(x(index)), y: plot.top, width: round(column), height: round(plot.bottom - plot.top) },
        })]
      : [],
  );

  // The window may climb to 70 °C to hold a wet month's rain; the degrees are
  // only numbered up to the ten above the warmest month, the rest of the left
  // axis being room for the rain.
  const warmest = labelTop(answer.months, answer.reference_months);
  const graduation = ticks(span).flatMap((degrees) => [
    svg("line", {
      className: "chart-rule",
      attrs: { x1: plot.from, x2: plot.to, y1: round(y(degrees)), y2: round(y(degrees)) },
    }),
    ...(degrees <= warmest
      ? [svg("text", {
          className: "chart-axis",
          text: present.temperature(degrees),
          attrs: { x: plot.from - 8, y: round(y(degrees) + 3), "text-anchor": "end" },
        })]
      : []),
    // No negative rain: the right axis stops at zero.
    ...(degrees >= 0
      ? [svg("text", {
          className: "chart-axis",
          text: String(degrees * RAIN_PER_DEGREE),
          attrs: { x: plot.to + 8, y: round(y(degrees) + 3) },
        })]
      : []),
  ]);

  const bars = (months, className, share, offset) =>
    months.flatMap((m, index) =>
      missing(m.precipitation) || m.precipitation === 0
        ? []
        : [svg("rect", {
            className,
            attrs: {
              x: round(x(index) + column * offset),
              y: round(y(m.precipitation / RAIN_PER_DEGREE)),
              width: round(column * share),
              height: round(base - y(m.precipitation / RAIN_PER_DEGREE)),
            },
          })],
    );

  const curve = (months, className, points) => {
    const at = months
      .map((m, index) => (missing(m.temperature_mean) ? null : [round(middle(index)), round(y(m.temperature_mean))]))
      .filter(Boolean);
    const d = at.map((p, k) => `${k === 0 ? "M" : "L"}${p.join(" ")}`).join(" ");
    return [
      svg("path", { className: `chart-line ${className}`, attrs: { d } }),
      ...(points
        ? at.map(([cx, cy]) => svg("circle", { className: `chart-point ${className}`, attrs: { cx, cy, r: 3 } }))
        : []),
    ];
  };

  const months = answer.months.map((m, index) =>
    svg("text", {
      className: "chart-month",
      text: texts.climate.months[m.month - 1],
      attrs: { x: round(middle(index)), y: plot.bottom + 22, "text-anchor": "middle" },
    }),
  );

  const units = [
    svg("text", { className: "chart-title", text: texts.units.celsius, attrs: { x: plot.from - 8, y: plot.top - 14, "text-anchor": "end" } }),
    svg("text", { className: "chart-title", text: texts.units.millimetres, attrs: { x: plot.to + 8, y: plot.top - 14 } }),
  ];

  // Stacking order: dry months under everything, the graduation, the reference
  // (bars then curve), the window's rain over it, its temperature on top.
  return svg(
    "svg",
    {
      className: "chart climate",
      attrs: {
        viewBox: `0 0 ${box.width} ${box.height}`,
        role: "img",
        "aria-label": texts.climate.label(years(answer.window), years(answer.reference)),
      },
    },
    [
      ...dry,
      ...graduation,
      svg("line", { className: "chart-baseline", attrs: { x1: plot.from, x2: plot.to, y1: round(base), y2: round(base) } }),
      // Side by side in each month: the reference on the left, the window on the right.
      ...bars(answer.reference_months, "climate-bar past", 0.36, 0.13),
      ...bars(answer.months, "climate-bar", 0.36, 0.51),
      ...curve(answer.reference_months, "past", false),
      ...curve(answer.months, "high", true),
      ...months,
      ...units,
    ],
  );
}

/** "2077-2091". */
export function years({ start_year: first, end_year: last }) {
  return `${first}-${last}`;
}

function round(value) {
  return Math.round(value * 10) / 10;
}
