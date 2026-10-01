/**
 * The file the visitor takes away.
 *
 * Two things are checked here that nothing else can check: that every row says
 * what produced it, and that the numbers survive the trip. The first is
 * CLAUDE.md rule 1 applied to a file rather than a screen — a temperature that
 * leaves this page with no origin beside it can be read as a measurement for as
 * long as the file exists. The second is arithmetic on strings, which is what
 * this module is.
 */

import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { fileName, toCsv } from "../../web/static/js/csv.js";
import { texts } from "../../web/static/js/i18n.js";

/** A served day, with everything the file writes. */
function day(over = {}) {
  return {
    date: "2046-07-14",
    origin: "simulated",
    source: "MRI_AGCM3_2_S",
    temperature_min: 21.4,
    temperature_max: 39,
    precipitation: 0,
    cloud_cover: 12.5,
    wind_speed_mean: 9,
    wet_bulb_mean: 27.8,
    humid_heat: 1,
    sky: "clear",
    ...over,
  };
}

const lines = (text) => text.split("\r\n");
const cells = (line) => line.split(";");

describe("the days as a file", () => {
  it("opens on the header the dictionary declares", () => {
    assert.deepEqual(cells(lines(toCsv([day()]))[0]), texts.export.columns());
  });

  it("borrows the labels the page already fixes", () => {
    const header = texts.export.columns();

    assert.ok(header.includes(`${texts.measure.windMean} (${texts.units.kilometresPerHour})`));
    assert.ok(header.some((name) => name.endsWith(`(${texts.units.celsius})`)));
  });

  it("writes one row a day, in the order of the header", () => {
    const [, row] = lines(toCsv([day()]));

    assert.deepEqual(cells(row), [
      "2046-07-14",
      "Simulation",
      "MRI_AGCM3_2_S",
      "21,4",
      "39",
      "0",
      "12,5",
      "9",
      "27,8",
      "Chaleur humide",
      "Dégagé",
    ]);
  });

  it("keeps the humid-heat level beside the figure it qualifies", () => {
    // The same leak the origin column closes, and the same remedy. A file
    // outlives the page it left, and "31,2" alone in a spreadsheet reads as
    // mild — a wet bulb has no scale a reader can call on. The word rides on
    // the row, against the number, where sorting and filtering cannot part them.
    const [, row] = lines(toCsv([day({ wet_bulb_mean: 31.2, humid_heat: 2 })]));
    const written = cells(row);

    assert.ok(written.includes("31,2"));
    assert.equal(written.at(-2), "Chaleur humide extrême");
  });

  it("writes nothing where there is nothing to report, and where there is no reading", () => {
    // Zero and null say different things in the contract and the same thing
    // here: a spreadsheet has no room for the difference, and the wet-bulb
    // column beside it already tells them apart by carrying a figure or a blank.
    const quiet = cells(lines(toCsv([day({ wet_bulb_mean: 18.3, humid_heat: 0 })]))[1]);
    const absent = cells(lines(toCsv([day({ wet_bulb_mean: null, humid_heat: null })]))[1]);

    assert.equal(quiet.at(-2), "");
    assert.equal(quiet.at(-3), "18,3");
    assert.equal(absent.at(-2), "");
    assert.equal(absent.at(-3), "");
  });

  it("names what produced every day, whatever produced it", () => {
    // The column CLAUDE.md rule 1 turns on. A row with an empty origin is a
    // number that can be taken for a measurement once the file is out of sight
    // of the page that wrote it.
    const days = [
      day({ origin: "observed" }),
      day({ origin: "simulated" }),
    ];
    const written = lines(toCsv(days))
      .slice(1, 3)
      .map((row) => cells(row)[1]);

    assert.deepEqual(written, ["Réanalyse", "Simulation"]);
    for (const name of written) assert.notEqual(name, "");
  });

  it("leaves a missing reading empty rather than filling it", () => {
    const [, row] = lines(toCsv([day({ temperature_min: null, sky: null })]));

    assert.equal(cells(row)[3], "");
    assert.equal(cells(row).at(-1), "");
    // And the row still has every column: an empty cell, not a missing one.
    assert.equal(cells(row).length, texts.export.columns().length);
  });

  it("writes a decimal the way the file's separator obliges", () => {
    // Semicolons and commas go together: a decimal point here would be read as
    // a French thousands separator, and 21,4 as 214.
    const [, row] = lines(toCsv([day({ temperature_max: 8.5 })]));

    assert.equal(cells(row)[4], "8,5");
    assert.ok(!row.includes("8.5"));
  });

  it("quotes a value that would otherwise shift every column after it", () => {
    const [, row] = lines(toCsv([day({ source: "essai;deux" })]));

    assert.ok(row.includes('"essai;deux"'));
    assert.equal(cells(row).length, texts.export.columns().length + 1, "the split sees the quotes");
  });

  it("ends on a line ending, and uses the one every spreadsheet accepts", () => {
    const text = toCsv([day(), day({ date: "2046-07-15" })]);

    assert.ok(text.endsWith("\r\n"));
    assert.equal(lines(text).length, 4, "header, two days, and the empty tail");
    assert.ok(!text.includes("\n\n"));
  });

  it("writes a header and nothing else for a series with no day", () => {
    assert.deepEqual(lines(toCsv([])), [texts.export.columns().join(";"), ""]);
  });
});

describe("what the file is called", () => {
  it("carries the place and the range", () => {
    assert.equal(fileName("Brest", "2046-07-01", "2046-07-31"), "meteo-brest-2046-07-01-2046-07-31.csv");
  });

  it("takes the accents and the spaces out of a place name", () => {
    // The name travels to filesystems this page knows nothing about, and the
    // place is whatever the visitor typed.
    assert.equal(
      fileName("Saint-Étienne du Rouvray", "2046-01-01", "2046-01-05"),
      "meteo-saint-etienne-du-rouvray-2046-01-01-2046-01-05.csv",
    );
  });

  it("stays a name when there is no place to name", () => {
    // The place comes from the query string, which can carry anything or
    // nothing; a name ending on a stray dash is still a name, but this one does
    // not.
    assert.equal(fileName("", "2046-01-01", "2046-01-05"), "meteo-2046-01-01-2046-01-05.csv");
    assert.equal(fileName("!!!", "2046-01-01", "2046-01-05"), "meteo-2046-01-01-2046-01-05.csv");
  });
});
