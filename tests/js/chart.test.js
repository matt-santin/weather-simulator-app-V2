/**
 * The chart: its two axes, its holes, and the mark it shares with the strip.
 *
 * What is checked here is what a look at the page cannot check. A curve drawn
 * across a missing day looks exactly like a curve drawn across a real one — the
 * failure is invisible by construction, which is the reason the geometry is
 * built by a module that answers outside a browser.
 *
 * The band ladder is passed in as the API serves it. Written out as a literal it
 * would be a second copy of the scale, and these tests would go on passing the
 * day the boundaries moved.
 */

import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { byClass, install, walk } from "./dom-stub.js";

install();

const chartModule = await import("../../web/static/js/chart.js");
const {
  BOX,
  RAIN_FLOOR_MM,
  chart,
  cumulative,
  cumulativeCeiling,
  edgeOf,
  frame,
  hasSoil,
  SOIL_TICKS,
  middleOf,
  rainCeiling,
  rainTicks,
  runs,
  temperatureWindow,
  ticks,
} = chartModule;
const { texts } = await import("../../web/static/js/i18n.js");
const present = await import("../../web/static/js/present.js");

/** The ladder as /api/config serves it: eight boundaries, five degrees apart. */
const SCALE = { edges: [5, 10, 15, 20, 25, 30, 35, 40], step: 5 };

/** A day of the series, as /api/days serves one. */
function day(date, origin, extra = {}) {
  return {
    date,
    origin,
    source: origin === "simulated" ? "MRI_AGCM3_2_S" : "era5",
    temperature_min: 14.2,
    temperature_max: 27.6,
    precipitation: 0.4,
    cloud_cover: 22.4,
    wind_speed_max: 31.0,
    sky: "cloudy",
    temperature_min_band: 2,
    temperature_max_band: 5,
    ...extra,
  };
}

/** A run of days from the same month, all observed. */
function series(count, extra = () => ({})) {
  return Array.from({ length: count }, (_, index) =>
    day(`2026-08-${String(index + 1).padStart(2, "0")}`, "observed", extra(index)),
  );
}

describe("the temperature axis", () => {
  it("snaps to the boundaries around the period, with half a step of air", () => {
    const days = series(3, (index) =>
      index === 0
        ? { temperature_min: 12.4, temperature_max: 21.0 }
        : { temperature_min: 16.0, temperature_max: 28.9 },
    );

    // 12,4 sits in the 10-15 band and 28,9 in the 25-30 one.
    assert.deepEqual(temperatureWindow(days, SCALE.step), { bottom: 7.5, top: 32.5 });
  });

  it("keeps a reading that lands exactly on a boundary off the frame", () => {
    const days = series(1, () => ({ temperature_min: 15.0, temperature_max: 30.0 }));

    assert.deepEqual(temperatureWindow(days, SCALE.step), { bottom: 12.5, top: 32.5 });
  });

  it("frames a freezing period below zero, the cold band being open", () => {
    const days = series(2, () => ({ temperature_min: -6.2, temperature_max: 2.0 }));

    assert.deepEqual(temperatureWindow(days, SCALE.step), { bottom: -12.5, top: 7.5 });
  });

  it("has nothing to frame when no day carries a temperature", () => {
    const days = series(4, () => ({ temperature_min: null, temperature_max: null }));

    assert.equal(temperatureWindow(days, SCALE.step), null);
  });
});

describe("the graduation", () => {
  it("rules the boundaries the window shows, and no other", () => {
    // The window runs 7,5 to 32,5.
    assert.deepEqual(ticks({ bottom: 7.5, top: 32.5 }, SCALE.edges, SCALE.step), [10, 15, 20, 25, 30]);
  });

  it("carries on under the ladder, whose coldest band has no boundary to rule", () => {
    // Everything below five degrees is one band, so a frozen period would be a
    // panel ruled once — at five — with nothing on zero.
    assert.deepEqual(ticks({ bottom: -12.5, top: 7.5 }, SCALE.edges, SCALE.step), [-10, -5, 0, 5]);
  });

  it("carries on over it too, the hottest band being open as well", () => {
    assert.deepEqual(ticks({ bottom: 32.5, top: 52.5 }, SCALE.edges, SCALE.step), [35, 40, 45, 50]);
  });

  it("writes the unit on the topmost number alone", () => {
    const days = series(2, () => ({ temperature_min: 12.4, temperature_max: 28.9 }));
    const numbers = byClass(chart(days, SCALE), "chart-axis").map((node) => node.textContent);

    assert.ok(numbers.includes(`30 ${texts.units.celsius}`));
    assert.equal(numbers.filter((text) => text.includes(texts.units.celsius)).length, 1);
  });
});

describe("the rain graduation", () => {
  it("rules on round millimetres, at most four intervals", () => {
    assert.deepEqual(rainTicks(RAIN_FLOOR_MM), [5, 10]);
    assert.deepEqual(rainTicks(23.8), [10, 20]);
    assert.deepEqual(rainTicks(12), [5, 10]);
    assert.deepEqual(rainTicks(96), [25, 50, 75]);
  });

  it("never rules above the wettest day, which is where the panel stops", () => {
    for (const ceiling of [10, 11.2, 23.8, 40, 96, 250]) {
      assert.ok(Math.max(...rainTicks(ceiling)) <= ceiling, `ruled over ${ceiling}`);
    }
  });
});

describe("the rain axis", () => {
  it("takes the wettest day of the period", () => {
    const days = series(3, (index) => ({ precipitation: [0.4, 23.8, 2.0][index] }));

    assert.equal(rainCeiling(days), 23.8);
  });

  it("does not follow a dry period down, which would make a drizzle a downpour", () => {
    const damp = series(3, (index) => ({ precipitation: [0, 0.3, 0][index] }));
    const dry = series(3, () => ({ precipitation: 0 }));

    assert.equal(rainCeiling(damp), RAIN_FLOOR_MM);
    assert.equal(rainCeiling(dry), RAIN_FLOOR_MM);
  });

  it("stands on the floor when every reading is missing", () => {
    assert.equal(rainCeiling(series(2, () => ({ precipitation: null }))), RAIN_FLOOR_MM);
  });
});

describe("the running total", () => {
  /** The `y` of a point, read off the `d` of the path that drew it. */
  const heights = (node) =>
    byClass(node, "cumulative")
      .filter((mark) => mark.tag === "path")
      .flatMap((path) =>
        path.attrs.d.split(/[ML]/).filter(Boolean).map((pair) => Number(pair.trim().split(" ")[1])),
      );

  it("adds each day to the ones before it", () => {
    const days = series(4, (index) => ({ precipitation: [2, 0, 5, 1][index] }));

    assert.deepEqual(
      cumulative(days).map((run) => run.map(({ value }) => value)),
      [[2, 2, 7, 8]],
    );
  });

  it("breaks at a missing day rather than stepping over it", () => {
    // Carrying on would draw the total flat across the hole, which is exactly
    // what a dry day draws: the curve would be saying "no rain" where the series
    // means "no reading". The next run opens where the last known day left it.
    const days = series(4, (index) => ({ precipitation: [2, null, 5, 1][index] }));

    assert.deepEqual(
      cumulative(days).map((run) => run.map(({ index, value }) => [index, value])),
      [
        [[0, 2]],
        [
          [2, 7],
          [3, 8],
        ],
      ],
    );
  });

  it("has nothing to draw when not one day carries a reading", () => {
    assert.deepEqual(cumulative(series(3, () => ({ precipitation: null }))), []);
  });

  it("frames its panel on where it ends, under the same floor as the bars", () => {
    const wet = series(4, () => ({ precipitation: 30 }));
    const dry = series(4, () => ({ precipitation: 0.2 }));

    assert.equal(cumulativeCeiling(wet), 120);
    assert.equal(cumulativeCeiling(dry), RAIN_FLOOR_MM);
  });

  it("stands on its own baseline, which is nought and not a frame", () => {
    const days = series(4, (index) => ({ precipitation: [0, 0, 0, 12][index] }));
    const node = chart(days, SCALE);
    const geometry = frame(4);

    // The first three days total nothing, so the curve opens on the foot of its
    // own panel — not on the rain panel's, which is a whole gap higher up.
    assert.equal(heights(node)[0], geometry.cumul.base);
  });

  it("climbs to the top of its panel on the last day it knows", () => {
    const days = series(3, () => ({ precipitation: 20 }));
    const geometry = frame(3);

    // Sixty millimetres in three days: the ceiling is the total, so the curve
    // ends on the panel's own top.
    assert.equal(heights(chart(days, SCALE)).at(-1), geometry.cumul.base - BOX.cumul);
  });

  it("is drawn against its own ceiling, never against the bars'", () => {
    // Twelve millimetres a day for ten days: the bars are framed on 12 and the
    // total on 120. Drawn on the bars' scale the curve would leave the drawing
    // ten times over — the failure this panel exists to make impossible.
    const days = series(10, () => ({ precipitation: 12 }));
    const geometry = frame(10);
    const y = (value) => geometry.cumul.base - (value / 120) * BOX.cumul;

    assert.deepEqual(heights(chart(days, SCALE)).slice(0, 2), [y(12), y(24)]);
  });

  it("carries no dots, being arithmetic and not a reading", () => {
    // A dot on this drawing marks something a gauge recorded. No gauge ever
    // recorded a running total.
    const node = chart(series(20, () => ({ precipitation: 3 })), SCALE);
    const dots = byClass(node, "chart-point").filter((m) => m.className.includes("cumulative"));

    assert.equal(dots.length, 0);
  });
});

describe("the third panel", () => {
  it("is graduated by the same function as the rain, on its own ceiling", () => {
    // 120 mm of total against a wettest day of 12: the two panels are ruled by
    // one rule read twice — 5 and 10 up there, 50 and 100 down here.
    const node = chart(series(10, () => ({ precipitation: 12 })), SCALE);
    const written = (name) => byClass(byClass(node, name)[0], "chart-axis").map((m) => m.textContent);

    assert.deepEqual(written("chart-rain"), ["5,0", `10,0 ${texts.units.millimetres}`]);
    assert.deepEqual(written("chart-cumul"), ["50,0", `100,0 ${texts.units.millimetres}`]);
  });

  it("writes its numbers where the two panels above write theirs", () => {
    // One ladder of hairlines per panel, all spanning the plot, all numbered at
    // the same offset off the left edge: nothing here is a second scale hanging
    // off the side of another panel.
    const node = chart(series(10, () => ({ precipitation: 12 })), SCALE);
    const geometry = frame(10);

    for (const label of byClass(node, "chart-axis")) {
      assert.equal(label.attrs["text-anchor"], "end");
      assert.equal(Number(label.attrs.x), geometry.plot.from - 8);
    }
    for (const rule of byClass(node, "chart-rule")) {
      assert.equal(Number(rule.attrs.x1), geometry.plot.from);
      assert.equal(Number(rule.attrs.x2), geometry.plot.to);
    }
  });

  it("keeps its graduation when the period has nothing to add up", () => {
    // The rain panel draws its own ladder and no bars in that case; this one
    // draws its ladder and no curve. A drawing whose height followed the holes
    // in the series would change shape for a reason no reader can see.
    const blank = chart(series(3, () => ({ precipitation: null })), SCALE);
    const [panel] = byClass(blank, "chart-cumul");

    assert.equal(byClass(panel, "chart-line").length, 0);
    assert.equal(byClass(panel, "chart-rule").length, 2);
    // Three panels and the folded title of the cloud cover.
    assert.equal(byClass(blank, "chart-title").length, 4);
  });
});

describe("a hole in the series", () => {
  it("breaks a curve in two rather than drawing across it", () => {
    const days = series(5, (index) => (index === 2 ? { temperature_max: null } : {}));

    const stretches = runs(days, (item) => item.temperature_max);
    assert.deepEqual(
      stretches.map((run) => run.map(({ index }) => index)),
      [
        [0, 1],
        [3, 4],
      ],
    );
  });

  it("leaves a lone reading its dot and no segment to join it to anything", () => {
    const days = series(3, (index) => (index === 1 ? {} : { temperature_max: null }));
    const node = chart(days, SCALE);

    const high = (name) => byClass(node, name).filter((mark) => mark.className.includes("high"));
    assert.equal(high("chart-point").length, 1);
    assert.equal(high("chart-line").length, 0);
  });

  it("marks every day it drew, on both curves", () => {
    const days = series(12, (index) => (index === 4 ? { temperature_min: null } : {}));
    const node = chart(days, SCALE);

    const points = (name) => byClass(node, "chart-point").filter((m) => m.className.includes(name));
    assert.equal(points("high").length, 12);
    assert.equal(points("low").length, 11);
  });

  it("tells a missing reading from a dry day in the rain panel", () => {
    const days = series(3, (index) => ({ precipitation: [null, 0, 4.2][index] }));
    const node = chart(days, SCALE);

    // The dry day draws nothing, so the missing one has to draw something.
    assert.equal(byClass(node, "chart-gap").length, 1);
    assert.equal(byClass(node, "chart-bar").length, 1);
  });
});

describe("the seam", () => {
  it("falls on the same day the strip marks, and only where there is a crossing", () => {
    const crossing = [
      day("2026-08-01", "observed"),
      day("2026-08-02", "forecast"),
      day("2026-08-03", "simulated"),
    ];
    const geometry = frame(crossing.length);
    const [rule] = byClass(chart(crossing, SCALE), "chart-seam-rule");

    // Coordinates are written to the hundredth: a column edge rarely lands on a
    // round number, and the trailing digits are markup and nothing else.
    assert.ok(Math.abs(Number(rule.attrs.x1) - edgeOf(geometry, 2)) < 0.01);
    assert.equal(rule.attrs.x1, rule.attrs.x2);
  });

  it("is not drawn on a range that never leaves a bank", () => {
    const ahead = [day("2046-07-14", "simulated"), day("2046-07-15", "simulated")];
    const past = [day("2001-07-14", "observed"), day("2001-07-15", "observed")];

    assert.equal(byClass(chart(ahead, SCALE), "chart-seam-rule").length, 0);
    assert.equal(byClass(chart(past, SCALE), "chart-seam-rule").length, 0);
  });

  it("carries the words, the rule alone saying nothing to a reader", () => {
    const days = [day("2026-08-01", "observed"), day("2026-08-02", "simulated")];
    const [label] = byClass(chart(days, SCALE), "chart-seam-label");

    assert.equal(label.textContent, texts.results.seam);
  });
});

describe("the drawing as a whole", () => {
  it("is one SVG node carrying its own name", () => {
    const node = chart(series(10), SCALE);

    assert.equal(node.tag, "svg");
    assert.equal(node.attrs.role, "img");
    assert.equal(node.attrs["aria-label"], texts.chart.label(null));
    assert.equal(node.attrs.viewBox, `0 0 ${BOX.width} ${frame(10).height}`);
  });

  it("builds every mark in the SVG namespace", () => {
    const marks = walk(chart(series(6), SCALE)).filter((node) => node.tag !== undefined);

    assert.ok(marks.length > 6);
    for (const mark of marks) {
      assert.equal(mark.namespace, "http://www.w3.org/2000/svg", `${mark.tag} is not SVG`);
    }
  });

  it("says what each panel plots, over it", () => {
    const titles = byClass(chart(series(8), SCALE), "chart-title");

    assert.deepEqual(
      titles.map((node) => node.textContent),
      [texts.chart.temperatures, texts.chart.precipitation, texts.chart.sky, texts.chart.cumulative],
    );
    // Over the plot, not in it: each sits above the panel it names.
    assert.ok(Number(titles[0].attrs.y) < frame(8).temperature.top);
    assert.ok(Number(titles[1].attrs.y) < frame(8).rain.top);
    assert.ok(Number(titles[2].attrs.y) < frame(8).cumul.top);
  });

  it("stands each panel on its own axis of dates", () => {
    const geometry = frame(10);
    const feet = byClass(chart(series(10), SCALE), "chart-baseline").map((line) =>
      Number(line.attrs.y1),
    );

    // One under each panel, all three spanning the plot.
    assert.deepEqual(feet, [geometry.temperature.bottom, geometry.rain.base, geometry.cumul.base]);
  });

  it("writes no number on the temperature axis, which is a frame and not a zero", () => {
    // The foot of that panel falls on whatever half-step the window snapped to.
    // Numbering it would put a value on the drawing that names nothing.
    const days = series(4, () => ({ temperature_min: 12.4, temperature_max: 28.9 }));
    const written = byClass(chart(days, SCALE), "chart-axis").map((node) => node.textContent);

    // The window runs 7,5 to 32,5; the lowest number on it is the first
    // boundary inside, one hairline above the foot.
    assert.equal(written[0], "10");
    assert.ok(!written.includes("7,5"));
  });

  it("marks the 1st, the 10th and the 20th, and no other day", () => {
    // Twenty-five days of August: three marks, in order, and nothing between —
    // once under each of the three panels, each dated at its own foot.
    const node = chart(series(25), SCALE);
    const written = byClass(node, "chart-date").map((mark) => mark.textContent);

    assert.deepEqual(written, ["1", "10", "20", "1", "10", "20", "1", "10", "20"]);
    // One tick per number, carrying the eye up to the column it names.
    assert.equal(byClass(node, "chart-tick").length, 9);
  });

  it("dates the three panels at the same days and the same x", () => {
    const geometry = frame(25);
    const ticks = byClass(chart(series(25), SCALE), "chart-tick");
    const rows = [ticks.slice(0, 3), ticks.slice(3, 6), ticks.slice(6)];

    // One axis read three times: the columns must line up exactly, or the rows
    // would be three different readings of the period.
    for (const row of rows) {
      assert.deepEqual(
        row.map((tick) => tick.attrs.x1),
        rows[0].map((tick) => tick.attrs.x1),
      );
    }
    // Each row hangs off its own panel's foot, never inside one.
    assert.deepEqual(
      rows.map((row) => Number(row[0].attrs.y1)),
      [geometry.temperature.bottom, geometry.rain.base, geometry.cumul.base],
    );
  });

  it("places a mark over the middle of its own day", () => {
    const geometry = frame(25);
    const [tick] = byClass(chart(series(25), SCALE), "chart-tick");

    // The 1st is the first column; its dot sits at the middle, and so does this.
    assert.ok(Math.abs(Number(tick.attrs.x1) - middleOf(geometry, 0)) < 0.01);
  });

  it("leaves a line of air in every gap, between a row of dates and a title", () => {
    // A row lives in the gap between two panels, where the lower title also
    // hangs, and not overlapping is not enough: a title that sits just under an
    // axis reads as belonging to the axis. Measured on the render — at 36 the
    // capitals landed on the digits' descenders, at 48 they cleared and still
    // read as one block. Forty is a full line of text between the two baselines.
    //
    // Checked in both gaps: a third panel means a second place this can go
    // wrong, and it would go wrong invisibly in the one nobody re-measured.
    // Measured from the *lowest* row of the panel above, which is the row of
    // month names since they were repeated under every panel — measuring the
    // numbers would leave the names to collide with the title unwatched.
    const geometry = frame(25);
    const gaps = [
      [geometry.temperature.months, geometry.rain.top],
      [geometry.rain.months, geometry.cumul.top],
    ];

    for (const [row, top] of gaps) {
      assert.ok(top - 12 - row >= 40, `${top - 12 - row}`);
    }
  });

  it("invents no day to carry a round number", () => {
    // A range opening on the 21st has no 1st, no 10th and no 20th of that month.
    const days = Array.from({ length: 8 }, (_, index) =>
      day(`2026-08-${21 + index}`, "observed"),
    );

    assert.deepEqual(byClass(chart(days, SCALE), "chart-date"), []);
  });

  it("marks the same days again in the next month", () => {
    const days = [
      ...Array.from({ length: 3 }, (_, i) => day(`2026-08-${29 + i}`, "observed")),
      ...Array.from({ length: 12 }, (_, i) =>
        day(`2026-09-${String(i + 1).padStart(2, "0")}`, "observed"),
      ),
    ];
    const written = byClass(chart(days, SCALE), "chart-date").map((mark) => mark.textContent);

    // Two marks a panel, three panels: the 1st and the 10th of September, the
    // three days of August the range opens on carrying none.
    assert.deepEqual(written, ["1", "10", "1", "10", "1", "10"]);
  });

  it("names the months where they turn, once each and under every panel", () => {
    // Named once under the lowest panel, the row above it read "1, 10, 20, 1,
    // 10" and there was no telling which 1 was which without leaving the panel
    // being read. Each axis now carries its own two rows: numbers, then names.
    const days = [
      ...series(3),
      day("2026-09-01", "observed"),
      day("2026-09-02", "observed"),
    ];
    const names = byClass(chart(days, SCALE), "chart-month").map((node) => node.textContent);

    assert.deepEqual(names, ["août", "septembre", "août", "septembre", "août", "septembre"]);
  });

  it("puts the names of a panel under its own numbers, never in the next panel", () => {
    const geometry = frame(25);
    const rows = [geometry.temperature, geometry.rain, geometry.cumul];
    const feet = [geometry.temperature.bottom, geometry.rain.base, geometry.cumul.base];

    for (const [index, row] of rows.entries()) {
      assert.ok(row.dates > feet[index], "the numbers hang below their own foot");
      assert.ok(row.months > row.dates, "the names sit under the numbers");
    }
    // The lowest row of the temperature panel still clears the rain panel.
    assert.ok(geometry.temperature.months < geometry.rain.top);
    assert.ok(geometry.rain.months < geometry.cumul.top);
  });

  it("says nothing above the days: no total, no average, no count", () => {
    const node = chart(series(20), SCALE);
    const written = walk(node)
      .map((child) => child.textContent)
      .filter(Boolean);

    // What is written on the chart is the two titles, the axes, the months, the
    // seam and the name of the cumulative curve. Any other number would be an
    // aggregate, which docs/application.md refuses — and the running total is
    // now the one it admits, on the arbitration recorded there.
    const allowed = new Set([
      texts.results.seam,
      texts.chart.temperatures,
      texts.chart.precipitation,
      texts.chart.cumulative,
      // The cloud cover panel: its title and the names of its three bands.
      texts.chart.sky,
      ...Object.values(texts.chart.skyZones),
      ...["clear", "cloudy", "overcast"].map((kind) => present.SKY[kind].emoji),
      ...byClass(node, "chart-axis").map((child) => child.textContent),
      ...byClass(node, "chart-date").map((child) => child.textContent),
      ...byClass(node, "chart-month").map((child) => child.textContent),
    ]);
    for (const text of written) {
      assert.ok(allowed.has(text), `unexpected text on the chart: "${text}"`);
    }
  });
});

describe("the normals laid under the days", () => {
  const LABEL = "Normales 1991-2020";
  /** Normals of the same dates, so the two can be compared slot by slot. */
  const past = (count, extra = () => ({})) =>
    Array.from({ length: count }, (_, index) =>
      day(`1991-08-${String(index + 1).padStart(2, "0")}`, "observed", extra(index)),
    );

  it("frames one window over both years", () => {
    // The compared year is colder than the drawn one at both ends. A window
    // framed on the drawn year alone would put its curves outside the panel.
    const days = series(10, () => ({ temperature_min: 18, temperature_max: 28 }));
    const cold = past(10, () => ({ temperature_min: 2, temperature_max: 11 }));

    const alone = temperatureWindow(days, SCALE.step);
    const both = temperatureWindow([...days, ...cold], SCALE.step);

    assert.ok(both.bottom < alone.bottom);
    // And the drawing frames on the second, not the first.
    const numbers = byClass(chart(days, SCALE, { compared: cold }), "chart-axis").map((node) =>
      Number(node.textContent.replace(",", ".").replace(/[^\d.-]/g, "")),
    );
    assert.ok(Math.min(...numbers) <= 5);
  });

  it("draws two grey curves and not one dot", () => {
    const node = chart(series(10), SCALE, { compared: past(10) });

    // Paths only: the legend borrows the same class for its two sample edges,
    // deliberately — one declaration of the colour and the width, not two — and
    // those are `line` elements. The running total is grey too and is counted
    // on its own panel, below.
    const lines = byClass(node, "chart-line").filter(
      (mark) =>
        mark.className.includes("past") &&
        !mark.className.includes("cumulative") &&
        mark.tag === "path",
    );
    assert.equal(lines.length, 2, "a maximum and a minimum");

    const dots = byClass(node, "chart-point").filter((mark) => mark.className.includes("past"));
    assert.equal(dots.length, 0, "the dot is the mark of the year asked for");
  });

  it("leaves the drawn year its own dots, all of them", () => {
    const plain = byClass(chart(series(10), SCALE), "chart-point").length;
    const compared = byClass(chart(series(10), SCALE, { compared: past(10) }), "chart-point")
      .length;

    assert.equal(compared, plain);
  });

  it("breaks the grey curve where the compared year has no day", () => {
    // The 29th of February, or any day the older year simply did not serve.
    const compared = past(10);
    compared[4] = null;

    const lines = byClass(chart(series(10), SCALE, { compared }), "chart-line").filter((mark) =>
      mark.className.includes("past high"),
    );
    // Two strokes rather than one line crossing a day that has no reading.
    assert.equal(lines.length, 2);
  });

  it("fills the compared year, and nothing at all without one", () => {
    // A panel showing one year shows two curves and the air between them. The
    // one fill this drawing has left is reserved for saying *older year*, so a
    // chart on its own carries none — the pale ribbon of the drawn year is gone.
    assert.equal(byClass(chart(series(10), SCALE), "chart-past-band").length, 0);

    const band = byClass(chart(series(10), SCALE, { compared: past(10) }), "chart-past-band");
    // One on the panel and one in the legend: the sample is the same fill.
    assert.equal(band.filter((mark) => mark.tag === "path").length, 1);
  });

  it("breaks the band where the compared year has no day", () => {
    const compared = past(10);
    compared[4] = null;

    const shapes = byClass(chart(series(10), SCALE, { compared }), "chart-past-band").filter(
      (mark) => mark.tag === "path",
    );
    // Two shapes rather than one spanning a day the older year never served.
    assert.equal(shapes.length, 2);
  });

  it("fills between the two readings of the compared year, and only those", () => {
    // The band has to be the compared year's own spread. A day carrying one
    // reading and not the other cannot be filled at all.
    const compared = past(10, (index) => (index === 3 ? { temperature_max: null } : {}));

    const shapes = byClass(chart(series(10), SCALE, { compared }), "chart-past-band").filter(
      (mark) => mark.tag === "path",
    );
    assert.equal(shapes.length, 2);
  });

  it("names the band on the drawing, in the margin above the plot", () => {
    const node = chart(series(10), SCALE, { compared: past(10), label: LABEL });
    const [written] = byClass(node, "chart-legend-label");

    assert.equal(written.textContent, LABEL);
    // Above the panel, where the window guarantees no mark can be: a legend
    // anchored to the band itself would have to dodge whichever curve is there.
    assert.ok(Number(written.attrs.y) < frame(10).temperature.top);
    // And right-anchored, clear of the title on the same line.
    assert.equal(written.attrs["text-anchor"], "end");
    assert.ok(Number(written.attrs.x) > frame(10).plot.to - 60);

    assert.equal(byClass(chart(series(10), SCALE), "chart-legend-label").length, 0);
    // No label without normals to name, even if one is passed.
    assert.equal(byClass(chart(series(10), SCALE, { label: LABEL }), "chart-legend-label").length, 0);
  });

  it("names the normals in its own label too", () => {
    const node = chart(series(10), SCALE, { compared: past(10), label: LABEL });

    assert.equal(node.attrs["aria-label"], texts.chart.label(LABEL));
    assert.match(node.attrs["aria-label"], /1991-2020/);
  });

  it("adds the label to the drawing and nothing else with it", () => {
    // The list of what may be written here gained one entry, and that was a
    // deliberate act rather than a slip: a year names a mark, the way the seam
    // label names a crossing. What the rule was written against — a total, an
    // average, a count, an extreme of the range — is still refused, and this
    // checks the widening did not let anything else through with it.
    const node = chart(series(20), SCALE, { compared: past(20), label: LABEL });
    const written = walk(node)
      .map((child) => child.textContent)
      .filter(Boolean);

    const allowed = new Set([
      texts.results.seam,
      texts.chart.temperatures,
      texts.chart.precipitation,
      texts.chart.cumulative,
      // The cloud cover panel: its title and the names of its three bands.
      texts.chart.sky,
      ...Object.values(texts.chart.skyZones),
      ...["clear", "cloudy", "overcast"].map((kind) => present.SKY[kind].emoji),
      LABEL,
      ...byClass(node, "chart-axis").map((child) => child.textContent),
      ...byClass(node, "chart-date").map((child) => child.textContent),
      ...byClass(node, "chart-month").map((child) => child.textContent),
    ]);
    for (const text of written) {
      assert.ok(allowed.has(text), `unexpected text on the chart: "${text}"`);
    }
  });

  it("totals the normals under the days, and names them there too", () => {
    const days = series(10, () => ({ precipitation: 1 }));
    const wet = past(10, () => ({ precipitation: 20 }));
    const node = chart(days, SCALE, { compared: wet, label: LABEL });

    const totals = byClass(node, "cumulative").filter((mark) => mark.tag === "path");
    // One run apiece, the grey first so the days run over it.
    assert.equal(totals.length, 2);
    assert.ok(totals[0].className.includes("past"));
    assert.ok(!totals[1].className.includes("past"));

    // Ten days at 20 mm is 200 mm of total, and the axis has to reach it.
    assert.equal(cumulativeCeiling(days, wet), 200);

    // One label on the temperatures, one on the total, on the same vertical.
    const geometry = frame(10);
    const labels = byClass(node, "chart-legend-label");
    assert.deepEqual(
      labels.map((label) => Number(label.attrs.y)),
      [geometry.temperature.top, geometry.cumul.top].map((top) => top - 12),
    );
    assert.equal(new Set(labels.map((label) => label.attrs.x)).size, 1);
  });

  it("draws no grey bars on the daily rain", () => {
    const node = chart(series(10, () => ({ precipitation: 1 })), SCALE, {
      compared: past(10, () => ({ precipitation: 5 })),
      label: LABEL,
    });

    assert.deepEqual(
      byClass(node, "chart-bar").filter((bar) => bar.className.includes("past")),
      [],
    );
  });
});

describe("snow on the ground, on the rain panel", () => {
  // Days 3 to 5 and day 8 of ten: two runs.
  const on = new Set([2, 3, 4, 7]);
  const days = series(10, (index) => ({ snow_on_ground: on.has(index) }));
  const node = chart(days, SCALE);
  const geometry = frame(days.length);
  const grounds = byClass(node, "chart-snow").filter((mark) => !mark.className.includes("sample"));

  it("lays one ground per unbroken run, as wide as the run and as tall as the panel", () => {
    assert.equal(grounds.length, 2);
    const [long, short] = grounds;
    assert.equal(Number(long.attrs.x), Math.round(edgeOf(geometry, 2) * 100) / 100);
    assert.equal(Number(long.attrs.width), Math.round(3 * geometry.column * 100) / 100);
    assert.equal(Number(short.attrs.width), Math.round(geometry.column * 100) / 100);
    assert.equal(Number(long.attrs.y), geometry.rain.top);
    assert.equal(Number(long.attrs.height), BOX.rain);
  });

  it("names it on the title line, and in the sentence of the drawing", () => {
    assert.ok(byClass(node, "chart-legend-label").some((label) => label.textContent === texts.chart.snow));
    assert.equal(node.attrs["aria-label"], texts.chart.label(null, true));
  });

  it("draws and names nothing where no day has snow, known or not", () => {
    for (const quiet of [series(10), series(10, () => ({ snow_on_ground: false }))]) {
      const plain = chart(quiet, SCALE);
      assert.equal(byClass(plain, "chart-snow").length, 0);
      assert.equal(byClass(plain, "chart-legend-label").length, 0);
      assert.equal(plain.attrs["aria-label"], texts.chart.label(null));
    }
  });
});

describe("the water left in the soil", () => {
  const days = series(10, (index) => ({ soil_water: index === 4 ? null : 100 - 10 * index }));
  const node = chart(days, SCALE);
  const geometry = frame(10, BOX, true);

  it("is a fourth panel under the total, as tall as BOX says", () => {
    assert.equal(node.attrs.viewBox, `0 0 ${BOX.width} ${geometry.height}`);
    assert.equal(geometry.soil.top, frame(10).cumul.base + BOX.gap);
    assert.equal(geometry.soil.base - geometry.soil.top, BOX.soil);
    assert.equal(geometry.height, frame(10).height + BOX.gap + BOX.soil);
    assert.ok(byClass(node, "chart-title").some((t) => t.textContent === texts.chart.soil));
  });

  it("is drawn on a fixed axis from 0 to 100 %, and breaks where a day has no value", () => {
    const areas = byClass(node, "chart-soil");
    assert.equal(areas.length, 2);
    const y = (value) => geometry.soil.base - (value / 100) * BOX.soil;
    assert.ok(areas[0].attrs.d.includes(` ${y(100)} `));
    assert.ok(areas[1].attrs.d.endsWith(`${geometry.soil.base} Z`));
    const written = byClass(node, "chart-soil-panel")[0];
    const labels = byClass(written, "chart-axis").map((t) => t.textContent);
    assert.deepEqual(labels, ["0", ...SOIL_TICKS.slice(0, -1).map(String), `100 ${texts.units.percent}`]);
  });

  it("names itself in the sentence of the drawing, and runs the seam down to its foot", () => {
    assert.equal(node.attrs["aria-label"], texts.chart.label(null, false, true));
    assert.equal(geometry.last, geometry.soil.base);
  });

  it("carries the normal as a grey line, and its name, when the normals are shown", () => {
    const normals = series(10, () => ({ soil_water: 60 }));
    const drawn = chart(days, SCALE, { compared: normals, label: "1991-2020" });
    const panel = byClass(drawn, "chart-soil-panel")[0];
    const grey = byClass(panel, "past");
    assert.equal(grey.length, 1);
    const y = Math.round((geometry.soil.base - 0.6 * BOX.soil) * 100) / 100;
    assert.ok(grey[0].attrs.d.includes(` ${y}`));
    const legends = byClass(drawn, "chart-legend");
    assert.equal(legends.length, 3);
    assert.equal(byClass(chart(days, SCALE, { compared: series(10), label: "1991-2020" }), "chart-legend").length, 2);
  });

  it("is not drawn when the server serves no soil water", () => {
    for (const plain of [series(10), series(10, () => ({ soil_water: null }))]) {
      const drawn = chart(plain, SCALE);
      assert.equal(byClass(drawn, "chart-soil").length, 0);
      assert.equal(drawn.attrs.viewBox, `0 0 ${BOX.width} ${frame(10).height}`);
      assert.equal(hasSoil(plain), false);
    }
  });
});

describe("the folded total and soil panels", () => {
  const { folds } = chartModule;
  const days = series(10, (index) => ({ soil_water: 100 - 5 * index }));
  const shut = { sky: false, cumul: false, soil: false };

  it("keeps the titles alone, and a shorter drawing", () => {
    const node = chart(days, SCALE, { open: shut });
    assert.equal(byClass(node, "chart-cumul").length, 0);
    assert.equal(byClass(node, "chart-soil").length, 0);
    const titles = byClass(node, "chart-title").map((title) => title.textContent);
    assert.ok(titles.includes(texts.chart.cumulative));
    assert.ok(titles.includes(texts.chart.soil));
    assert.ok(frame(10, BOX, true, shut).height < frame(10, BOX, true).height);
  });

  it("draws a panel once opened, the other staying folded", () => {
    const node = chart(days, SCALE, { open: { sky: false, cumul: true, soil: false } });
    assert.equal(byClass(node, "chart-cumul").length, 1);
    assert.equal(byClass(node, "chart-soil").length, 0);
    assert.equal(byClass(node, "chart-sky-panel").length, 0);
  });

  it("draws the cloud cover on 0 to 100 %, ruled at the bounds of the pictograms", () => {
    const cloudy = series(10, (index) => ({ cloud_cover: index * 10 }));
    const node = chart(cloudy, SCALE, { open: { sky: true, cumul: false, soil: false } });
    const [panel] = byClass(node, "chart-sky-panel");
    const geometry = frame(10, BOX, false, { sky: true, cumul: false, soil: false });
    const axis = byClass(panel, "chart-axis").map((label) => label.textContent);
    assert.deepEqual(axis, ["0", "30", "70", `100 ${texts.units.percent}`]);
    const rules = byClass(panel, "chart-rule").map((rule) => Number(rule.attrs.y1));
    assert.deepEqual(rules, [geometry.sky.base - 30, geometry.sky.base - 70]);
    assert.deepEqual(
      byClass(panel, "chart-zone").map((zone) => zone.textContent),
      Object.values(texts.chart.skyZones),
    );
    assert.deepEqual(
      byClass(panel, "chart-zone-icon").map((icon) => icon.textContent),
      ["clear", "cloudy", "overcast"].map((kind) => present.SKY[kind].emoji),
    );
    assert.equal(byClass(panel, "chart-sky").length, 1);
  });

  it("places one fold per panel, on its title line, the soil only where served", () => {
    const placed = folds(days, shut);
    assert.deepEqual(
      placed.map((fold) => [fold.key, fold.open]),
      [["sky", false], ["cumul", false], ["soil", false]],
    );
    assert.ok(placed[0].y < placed[1].y && placed[1].y < placed[2].y && placed[2].y < 1);
    assert.deepEqual(folds(series(10), shut).map((fold) => fold.key), ["sky", "cumul"]);
  });
});
