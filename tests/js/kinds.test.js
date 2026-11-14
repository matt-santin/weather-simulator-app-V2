/**
 * The kind mode of the home form: the words of the three kinds, the year the
 * server is asked about, and the draw.
 */

import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  DRAWN, KINDS, anyYearOf, dayOf, draw, drawAnother, epochLabel, kindLabels, kindsOf, record,
} from "../../web/static/js/kinds.js";
import { texts } from "../../web/static/js/i18n.js";

describe("kindLabels", () => {
  it("names every kind, a winter cold or mild", () => {
    for (const season of Object.keys(texts.season)) {
      const labels = kindLabels(season);
      assert.deepEqual(Object.keys(labels).sort(), [...kindsOf(season)].sort());
    }
    assert.equal(kindLabels("winter").warm, "Doux");
    assert.equal(kindLabels("summer").warm, "Chaud");
    assert.equal(kindLabels("summer").record, "Record de chaleur");
    assert.equal(kindLabels("winter").record, "Record de douceur");
    assert.equal(kindLabels("winter").coldRecord, "Record de froid");
    assert.equal(kindLabels("summer").coldRecord, "Record de fraîcheur");
  });
});

describe("epochLabel", () => {
  it("writes the name and the years", () => {
    assert.equal(epochLabel({ id: "old", first: 1970, last: 2010 }), "Ancien climat (1970-2010)");
    assert.equal(epochLabel({ id: "future", first: 2051, last: 2100 }), "Climat futur (2051-2100)");
  });
});

describe("anyYearOf", () => {
  it("takes the first served year of the epoch", () => {
    const years = [1994, 1995, 1996, 1997, 2027, 2028];
    assert.equal(anyYearOf({ first: 1996, last: 2025 }, years), 1996);
    assert.equal(anyYearOf({ first: 2027, last: 2056 }, years), 2027);
    assert.equal(anyYearOf({ first: 2071, last: 2100 }, years), null);
  });
});

describe("draw", () => {
  const ranked = { cool: [2001, 2005], normal: [2002], warm: [2003, 2004, 2010] };

  it("draws among the years of the kind asked for", () => {
    assert.equal(draw(ranked, "warm", () => 0), 2003);
    assert.equal(draw(ranked, "warm", () => 0.5), 2004);
    assert.equal(draw(ranked, "warm", () => 0.9999), 2010);
    assert.equal(draw(ranked, "cool", () => 0.6), 2005);
  });

  it("gives the record without drawing: the highest mean, the later year on a tie", () => {
    const epoch = { ...ranked, values: { 2001: 24.1, 2003: 29.8, 2004: 27.0, 2010: 29.8 } };
    assert.equal(record(epoch), 2010);
    assert.equal(draw(epoch, "record", () => 0), 2010);
    assert.equal(draw({ values: { 2003: 29.8, 2004: 27.0 } }, "record"), 2003);
    assert.equal(record({ values: {} }), null);
    assert.equal(draw(epoch, "coldRecord"), 2001);
    assert.equal(record({ values: { 2001: 20, 2002: 20 } }, -1), 2002);
  });

  it("answers null when there is none", () => {
    assert.equal(draw({ cool: [] }, "cool"), null);
    assert.equal(draw(undefined, "warm"), null);
  });
});

describe("the extreme days", () => {
  const ranked = {
    hottest: { year: 2087, date: "2087-07-12", value: 43.1 },
    coldest: { year: 2056, date: "2057-01-08", value: -14.2 },
  };

  it("are offered one per season: the hottest day, the coldest in winter", () => {
    assert.deepEqual(kindsOf("summer"), [...KINDS, "hottestDay"]);
    assert.deepEqual(kindsOf("winter"), [...KINDS, "coldestDay"]);
  });

  it("give their season and the day it opens on", () => {
    assert.equal(draw(ranked, "hottestDay"), 2087);
    assert.equal(dayOf(ranked, "hottestDay"), "2087-07-12");
    assert.equal(draw(ranked, "coldestDay"), 2056);
    assert.equal(dayOf(ranked, "coldestDay"), "2057-01-08");
    assert.equal(dayOf(ranked, "warm"), null);
    assert.equal(draw({}, "hottestDay"), null);
  });
});

describe("another year of the same kind", () => {
  const ranked = { warm: [2018, 2022, 2030], normal: [2015], values: { 2018: 28, 2022: 29, 2030: 28.5 } };

  it("is never the year shown", () => {
    for (const random of [() => 0, () => 0.5, () => 0.999]) {
      assert.notEqual(drawAnother(ranked, "warm", 2022, random), 2022);
    }
    assert.equal(drawAnother(ranked, "warm", 2022, () => 0), 2018);
    assert.equal(drawAnother(ranked, "warm", 2022, () => 0.999), 2030);
  });

  it("is null when the kind holds that year alone, or always gives the same", () => {
    assert.equal(drawAnother(ranked, "normal", 2015), null);
    assert.equal(drawAnother(ranked, "record", 2022), null);
    assert.equal(drawAnother(ranked, "hottestDay", 2022), null);
    assert.deepEqual(DRAWN, ["cool", "normal", "warm"]);
  });
});
