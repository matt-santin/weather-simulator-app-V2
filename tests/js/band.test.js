/**
 * The strip: what it shows, and where it puts its two reading marks.
 *
 * These are the rules that live in the interface rather than on the server —
 * the seam, the month markers, the card for a day without a sky class — so a
 * document is the only other thing holding them. Here they are executable.
 */

import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { byClass, install, reads, textOf, walk } from "./dom-stub.js";

// Before the import, not after: `el` reaches for the global on its first call.
install();

const { card, legend, sources, strip } = await import("../../web/static/js/band.js");
const { texts } = await import("../../web/static/js/i18n.js");

/** Every text under the first node carrying that class, in reading order. */
function said(node, name) {
  const [found] = byClass(node, name);
  return found ? walk(found).map((child) => child.textContent).join("") : undefined;
}

/** The cards alone, without the empty cells that open the calendar. */
const cards = (nodes) => nodes.filter((node) => node.className.split(" ").includes("card"));

/** A day of the series, as /api/days serves one. */
function day(date, origin, extra = {}) {
  return {
    date,
    origin,
    source: origin === "simulated" ? "MRI_AGCM3_2_S" : "era5",
    temperature_min: 14.2,
    temperature_max: 27.6,
    precipitation: 0.44,
    cloud_cover: 22.4,
    relative_humidity_mean: 63.4,
    wind_speed_mean: 8.4,
    wind_speed_max: 18.7,
    sky: "clear",
    ...extra,
  };
}

describe("the daily card", () => {
  const only = card(day("2046-07-14", "simulated"), true);

  it("carries the four measures, each one named", () => {
    // What a screen reader gets, in order — so each number arrives with a word.
    //
    // **The maximum comes first**, and the order is pinned here on purpose. The
    // card used to run "min · max" on one line; the results mock-up stacks them
    // and leads with the maximum, and what is read aloud follows what is seen
    // rather than keeping an order the eye no longer has. The degree sign rides
    // on each of the two now, which is what stacking costs.
    assert.equal(
      reads(only).replace(/\s+/g, " "),
      "juillet samedi 14/07 Maximale 28 °C Minimale 14 °C Dégagé " +
        "Précipitations 0,4 mm Humidité relative 63 % Vent moyen 8 km/h",
    );
  });

  it("carries one wind, the daily mean, and never a gust", () => {
    const spoken = reads(only);
    assert.match(spoken, /Vent moyen/);
    assert.doesNotMatch(spoken, /Vent maximal/);
    assert.doesNotMatch(spoken, /rafale/i);
  });

  it("doubles the pictogram with a written equivalent", () => {
    assert.equal(textOf(only, "card-emoji"), "☀️");
    assert.equal(textOf(only, "card-sky"), "Dégagé");
    // The emoji is hidden from screen readers; the written class is not.
    assert.equal(byClass(only, "card-emoji")[0].attrs["aria-hidden"], "true");
    assert.match(reads(only), /Dégagé/);
  });

  it("carries its source as an attribute, for diagnosing the seams", () => {
    assert.equal(only.attrs.title, "MRI_AGCM3_2_S");
  });

  it("carries the band of the maximum, which tints the whole card", () => {
    // The band arrives decided by the server; the card only writes it down.
    const banded = card(day("2046-07-14", "simulated", { temperature_max_band: 5 }), false);
    assert.equal(banded.attrs["data-band"], "5");
  });

  it("carries no band on a day with no maximum: a gap is not a shade of cold", () => {
    const blank = card(day("2046-07-14", "simulated", { temperature_max_band: null }), false);
    assert.equal(blank.attrs["data-band"], undefined);
  });
});

describe("a day with gaps", () => {
  const holed = card(
    day("2046-07-14", "observed", {
      temperature_max: null,
      precipitation: null,
      wind_speed_mean: null,
      sky: null,
    }),
    false,
  );

  it("shows a dash, never NaN or undefined", () => {
    const spoken = reads(holed);
    assert.doesNotMatch(spoken, /NaN|undefined|null/);
    assert.match(spoken, /—/);
  });

  it("says 'data missing' to anyone who cannot see the dash", () => {
    const labelled = walk(holed).filter(
      (node) => node.attrs["aria-label"] === texts.measure.missingLabel,
    );
    assert.equal(labelled.length, 3);
  });

  it("with no sky class, a label and no invented pictogram", () => {
    assert.equal(textOf(holed, "card-emoji"), "");
    assert.equal(textOf(holed, "card-sky"), "Ciel indéterminé");
  });
});

describe("the calendar", () => {
  it("opens with the month, then empty cells, so that each day falls under its weekday", () => {
    // 2046-07-12 is a Thursday: three cells, Monday to Wednesday, come first.
    const nodes = strip([day("2046-07-12", "observed"), day("2046-07-13", "observed")]);
    assert.deepEqual(
      nodes.map((node) => node.className),
      ["month-row", "pad", "pad", "pad", "card card--observed", "card card--observed"],
    );
    assert.equal(nodes[0].textContent, "juillet 2046");
  });

  it("opens each new month on a line of its own, under its weekday", () => {
    // 2046-07-31 is a Tuesday, 2046-08-01 a Wednesday: the week is cut, and
    // August picks up after two empty cells.
    const nodes = strip([day("2046-07-31", "observed"), day("2046-08-01", "observed")]);
    assert.deepEqual(
      nodes.map((node) => node.className),
      ["month-row", "pad", "card card--observed", "month-row", "pad", "pad", "card card--observed"],
    );
    assert.equal(nodes[3].textContent, "août 2046");
  });

  it("hides the month lines and the empty cells from screen readers", () => {
    const [month, pad] = strip([day("2046-07-12", "observed")]);
    assert.equal(month.attrs["aria-hidden"], "true");
    assert.equal(pad.attrs["aria-hidden"], "true");
  });

  it("adds no empty cell before a month starting on a Monday", () => {
    const nodes = strip([day("2046-07-09", "observed")]);
    assert.deepEqual(
      nodes.map((node) => node.className),
      ["month-row", "card card--observed"],
    );
  });

  it("shows the day of the month and reads the full date", () => {
    const [first, next] = cards(strip([day("2046-07-09", "observed"), day("2046-07-10", "observed")]));
    assert.equal(textOf(first, "card-date-short"), "9");
    assert.equal(textOf(next, "card-date-short"), "10");
    const only = first;
    assert.equal(byClass(only, "card-date-short")[0].attrs["aria-hidden"], "true");
    assert.equal(textOf(only, "card-date-long"), "lundi 09/07");
  });

  it("is empty when there are no days", () => {
    assert.deepEqual(strip([]), []);
  });
});

describe("the seam", () => {
  const days = [
    day("2026-08-03", "observed"),
    day("2026-08-04", "observed"),
    day("2026-08-05", "simulated"),
    day("2026-08-06", "simulated"),
  ];
  const seamed = (nodes) => nodes.filter((node) => node.className.includes("card--seam"));

  it("rides on the first simulated card, and on that one alone", () => {
    // A cell of its own would push every following day off its weekday.
    const nodes = cards(strip(days));
    assert.equal(nodes.length, 4);
    assert.deepEqual(seamed(nodes), [nodes[2]]);
    assert.equal(nodes[2].className, "card card--simulated card--seam");
  });

  it("is written, not only tinted", () => {
    // Colour alone must never be what carries the information.
    const [seam] = seamed(strip(days));
    assert.equal(textOf(seam, "card-seam"), texts.results.seamCard);
    assert.match(reads(seam), /simulation/);
  });

  it("does not appear on a range lying wholly in the past", () => {
    const past = strip([day("2024-06-03", "observed"), day("2024-06-04", "observed")]);
    assert.equal(seamed(past).length, 0);
  });

  it("nor on a range lying wholly in the model", () => {
    // No bank to leave: a marker on the very first card would announce a
    // passage that never happens. The warning at the top covers that case.
    const future = strip([day("2046-07-02", "simulated"), day("2046-07-03", "simulated")]);
    assert.equal(seamed(future).length, 0);
  });

  it("falls at the end of the forecast, not at tonight", () => {
    // The whole point of the IFS segment: tomorrow is weather, and the crossing
    // belongs where forecasting stops rather than where the calendar turns.
    const nodes = cards(
      strip([
        day("2026-08-11", "observed"),
        day("2026-08-12", "forecast"),
        day("2026-08-13", "forecast"),
        day("2026-08-14", "simulated"),
      ]),
    );
    assert.deepEqual(seamed(nodes), [nodes[3]]);
  });

  it("is still marked on a range that starts tomorrow", () => {
    // Forecast then simulated, never observed. Reading "observed" alone to
    // decide there was a bank to leave would let this crossing go unmarked.
    const nodes = strip([
      day("2026-08-12", "forecast"),
      day("2026-08-13", "forecast"),
      day("2026-08-14", "simulated"),
    ]);
    assert.equal(seamed(nodes).length, 1);
  });

  it("does not appear on a range that never leaves the forecast", () => {
    const ahead = strip([day("2026-08-12", "forecast"), day("2026-08-13", "forecast")]);
    assert.equal(seamed(ahead).length, 0);
  });
});

describe("the month marker", () => {
  it("writes the month name only where it turns", () => {
    const nodes = cards(
      strip([
        day("2046-07-30", "observed"),
        day("2046-07-31", "observed"),
        day("2046-08-01", "observed"),
      ]),
    );
    assert.deepEqual(
      nodes.map((node) => said(node, "card-month")),
      ["juillet", "", "août"],
    );
  });

  it("says the month in figures on every card, so scrolling never loses it", () => {
    // Naming it on every card was tried on 2026-09-08 and reversed the same day:
    // it answered the reader who scrolls past the turn, and cost the turn its
    // salience — a name among a run of identical names marks nothing. Two digits
    // on the date line say the month wherever the reader is, at no such price. A
    // cadence of one card in seven was the third candidate and fails on a narrow
    // window, which shows two cards at a time.
    const written = cards(
      strip([
        day("2046-07-30", "observed"),
        day("2046-07-31", "observed"),
        day("2046-08-01", "observed"),
      ]),
    ).map((node) => textOf(node, "card-date-long"));

    assert.deepEqual(written, ["lundi 30/07", "mardi 31/07", "mercredi 01/08"]);
  });

  it("names the month on the first card, whatever happens", () => {
    const [first] = cards(strip([day("2046-07-31", "observed")]));
    assert.equal(said(first, "card-month"), "juillet");
  });
});

describe("where the days come from", () => {
  const grid = {
    model: "EC-EARTH (r12i1p1) / SMHI-RCA4, CORDEX EUR-11, scénario RCP 4.5",
    reference: "ERA5-Land (températures), ERA5",
    calibration_start: "1970-01-01",
    calibration_end: "2005-12-31",
    projection_start: "2027-01-01",
    projection_end: "2100-12-31",
    step: 0.25,
    temperature_step: 0.1,
    generated: "2026-09-30",
  };

  it("gives the model, the periods, the step and the preparation date", () => {
    const said = sources(grid).map((node) => node.textContent);
    assert.deepEqual(said, [
      "Modèle climatique",
      "EC-EARTH (r12i1p1) / SMHI-RCA4, CORDEX EUR-11, scénario RCP 4.5",
      "Correction calibrée sur",
      "ERA5-Land (températures), ERA5",
      "Période de calibration",
      "1 janvier 1970 – 31 décembre 2005",
      "Période simulée",
      "1 janvier 2027 – 31 décembre 2100",
      "Pas de la grille",
      "0,1° (températures), 0,25°",
      "Données préparées le",
      "30 septembre 2026",
    ]);
  });

  it("says nothing when nothing was corrected", () => {
    assert.deepEqual(sources(null), []);
  });
});

describe("the humid-heat line", () => {
  const hot = (level, value) => day("2046-08-16", "simulated", { humid_heat: level, wet_bulb_mean: value });
  const calm = day("2046-08-17", "simulated", { humid_heat: 0, wet_bulb_mean: 18.2 });

  it("is absent from a strip that has nothing to mark", () => {
    // Which is every strip in France. The line costs a rule of height on ninety
    // cards, and a range that will never fill it must not pay for it: the peak
    // arrives on the response, so the decision is taken once for the strip.
    const nodes = strip([calm, calm], 0);

    assert.equal(nodes.flatMap((node) => byClass(node, "card-humid")).length, 0);
  });

  it("is reserved on every card as soon as one day carries it", () => {
    // The cards stretch to the tallest. A line on the one hot day of the range
    // would grow the others and shift the strip under the reader, so the empty
    // ones are rendered empty rather than left out — the answer the month line
    // above already gives to the same problem.
    const nodes = strip([calm, hot(1, 27.6), calm], 1);
    const lines = nodes.flatMap((node) => byClass(node, "card-humid"));

    assert.equal(lines.length, 3);
    assert.deepEqual(
      lines.map((line) => line.attrs["data-humid"]),
      [undefined, "1", undefined],
    );
    assert.equal(lines[0].textContent, "");
  });

  it("shows the figure, and never before the word that names it", () => {
    // The project owner asked for the number on 2026-09-07. What survives of the
    // arbitration it reverses is the order: a wet bulb has no scale a reader can
    // call on, and the card already carries two temperatures in large type, so a
    // bare third figure would read as a third air temperature. The word arrives
    // first and says which quantity this is.
    const line = byClass(card(hot(2, 31.4), false, true), "card-humid")[0];
    const seen = walk(line)
      .filter((node) => !node.className.split(" ").includes("sr-only"))
      .map((node) => node.textContent)
      .join("");

    assert.ok(seen.includes(texts.humidHeat.level[2]));
    assert.ok(seen.includes("31"));
    assert.ok(seen.indexOf(texts.humidHeat.level[2]) < seen.indexOf("31"));
  });

  it("rounds the figure as every other temperature on the card is rounded", () => {
    // `docs/application.md` fixes whole degrees for a temperature and a tenth for
    // a millimetre. A wet bulb is a temperature, and a second rounding rule for
    // one figure among three would be the divergence rule 3 is about.
    const line = byClass(card(hot(1, 27.6), false, true), "card-humid")[0];

    const written = walk(byClass(line, "card-humid-value")[0])
      .map((node) => node.textContent)
      .join("");

    assert.equal(written, `28${texts.units.celsius}`);
  });

  it("gives the figure to whoever cannot see the ink that carries the level", () => {
    // The tooltip needs a pointer, and the colour needs eyes. The reading goes
    // off-screen beside the word, which is what `measure` already does with the
    // label the card does not print.
    const line = byClass(card(hot(1, 27.6), false, true), "card-humid")[0];

    assert.match(reads(line), /28/);
    assert.equal(line.attrs.title, texts.humidHeat.reading("28"));
  });

  it("says nothing on a day with no reading, in a strip that reserves the line", () => {
    // Null is not zero: the day was not measured, and a card must no more invent
    // a level than it invents a sky class.
    const line = byClass(
      card(day("2046-08-18", "simulated", { humid_heat: null, wet_bulb_mean: null }), false, true),
      "card-humid",
    )[0];

    assert.equal(line.textContent, "");
    assert.equal(line.attrs["data-humid"], undefined);
  });
});

describe("the legend of the calendar", () => {
  it("has one chip per band, bounded by the server's edges", () => {
    const edges = [0, 5, 10, 15, 20, 25, 30, 35, 40];
    const [, list] = legend(edges).children;
    const chips = list.children;
    assert.equal(chips.length, edges.length + 1);
    assert.deepEqual(chips.map((chip) => chip.attrs["data-band"]), ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]);
    assert.equal(chips[0].textContent, "< 0");
    assert.equal(chips[1].textContent, "0-5");
    assert.equal(chips[9].textContent, "≥ 40");
  });
});
