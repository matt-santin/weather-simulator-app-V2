/**
 * The climate diagram: the two axes stay at the ratio of Bagnouls and Gaussen,
 * the dry months the server names are the ones tinted, and the window holds
 * both series.
 */

import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { byClass, install } from "./dom-stub.js";

install();
const { BOX, RAIN_PER_DEGREE, diagram, summary, ticks, window } = await import(
  "../../web/static/js/climate.js"
);

/** Twelve months, with optional overrides by index. */
const months = (make = () => ({})) =>
  Array.from({ length: 12 }, (_, index) => ({
    month: index + 1,
    temperature_mean: 10,
    temperature_min: 5,
    temperature_max: 15,
    precipitation: 60,
    dry: false,
    ...make(index),
  }));

const answer = (own, reference = months()) => ({
  window: { start_year: 2077, end_year: 2091, origin: "simulated", source: "CORDEX" },
  reference: { start_year: 1991, end_year: 2020, origin: "observed", source: "ERA5" },
  months: own,
  reference_months: reference,
});

describe("the climate diagram", () => {
  it("frames the window on the temperature and on half the rain", () => {
    // 150 mm of rain stands at 75 on the temperature axis: the window has to reach it.
    const wet = months((index) => (index === 0 ? { precipitation: 150 } : {}));
    assert.deepEqual(window(wet), { bottom: 0, top: 80 });
    // A cold month opens the window below zero, on the multiple of five.
    const cold = months((index) => (index === 0 ? { temperature_mean: -3.2 } : {}));
    assert.equal(window(cold).bottom, -5);
  });

  it("holds the reference in the same window", () => {
    const hot = months(() => ({ temperature_mean: 32 }));
    assert.equal(window(months(), hot).top, 40);
  });

  it("puts 20 mm level with 10 °C", () => {
    assert.equal(RAIN_PER_DEGREE, 2);
    const node = diagram(answer(months()));
    const axis = byClass(node, "chart-axis");
    // The left axis is anchored at its end, the right one is not.
    const left = axis.find((label) => label.textContent === "10" && label.attrs["text-anchor"] === "end");
    const right = axis.find((label) => label.textContent === "20" && !label.attrs["text-anchor"]);
    assert.equal(left.attrs.y, right.attrs.y);
  });

  it("tints the months the server calls dry, and only those", () => {
    const own = months((index) => (index === 6 || index === 7 ? { dry: true } : {}));
    const node = diagram(answer(own));
    const dry = byClass(node, "climate-dry");
    assert.equal(dry.length, 2);
    const column = (BOX.width - BOX.left - BOX.right) / 12;
    assert.equal(Number(dry[0].attrs.x), Math.round((BOX.left + column * 6) * 10) / 10);
  });

  it("draws the reference in grey, without dots", () => {
    const node = diagram(answer(months()));
    assert.equal(byClass(node, "climate-bar").filter((bar) => bar.className.includes("past")).length, 12);
    assert.equal(byClass(node, "chart-point").filter((dot) => dot.className.includes("past")).length, 0);
    assert.equal(byClass(node, "chart-point").length, 12);
  });

  it("rules every 5 °C, or every 10 on a tall window", () => {
    assert.deepEqual(ticks({ bottom: 0, top: 20 }), [0, 5, 10, 15, 20]);
    assert.deepEqual(ticks({ bottom: -10, top: 80 }), [-10, 0, 10, 20, 30, 40, 50, 60, 70, 80]);
    // A window opening at -5 on a step of 10 still rules zero.
    assert.deepEqual(ticks({ bottom: -5, top: 80 }), [0, 10, 20, 30, 40, 50, 60, 70, 80]);
  });

  it("sums the year and lists the dry months", () => {
    const own = months((index) => (index === 6 ? { dry: true } : {}));
    assert.deepEqual(summary(own), { temperature: 10, precipitation: 720, dry: [7] });
  });
});

describe("the left axis", () => {
  it("numbers the degrees only up to the ten above the warmest month", async () => {
    const { labelTop } = await import("../../web/static/js/climate.js");
    const wet = months((index) => (index === 9 ? { precipitation: 140, temperature_mean: 26 } : {}));
    assert.equal(labelTop(wet), 30);
    const node = diagram(answer(wet));
    const left = byClass(node, "chart-axis").filter((label) => label.attrs["text-anchor"] === "end");
    assert.deepEqual(left.map((label) => label.textContent).at(-1), "30");
  });
});

describe("the rain bars", () => {
  it("stand side by side, the reference on the left", () => {
    const node = diagram(answer(months()));
    const bars = byClass(node, "climate-bar");
    const grey = bars.find((bar) => bar.className.includes("past"));
    const blue = bars.find((bar) => !bar.className.includes("past"));
    // Same month (the first), no overlap.
    assert.ok(Number(grey.attrs.x) + Number(grey.attrs.width) <= Number(blue.attrs.x));
  });
});
