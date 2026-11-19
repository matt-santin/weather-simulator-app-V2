/**
 * "À voir aussi": the next season, the typical season of the other period and
 * the record of the cards at the foot of the results page.
 */

import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  allValues, degrees, nextSeason, previousSeason, recordPick, recordWords, typical, typicalSpan,
} from "../../web/static/js/suggest.js";
import { texts } from "../../web/static/js/i18n.js";

describe("nextSeason and previousSeason", () => {
  it("walk the year, a winter opening in its first year", () => {
    assert.deepEqual(nextSeason("summer", 2063), { season: "autumn", year: 2063 });
    assert.deepEqual(nextSeason("autumn", 2063), { season: "winter", year: 2063 });
    assert.deepEqual(nextSeason("winter", 2063), { season: "spring", year: 2064 });
    assert.deepEqual(previousSeason("spring", 2064), { season: "winter", year: 2063 });
    assert.deepEqual(previousSeason("summer", 2063), { season: "spring", year: 2063 });
    assert.equal(nextSeason("monsoon", 2063), null);
  });
});

/** Thirty years of 1991-2020 around 26, 2005 the nearest the mean. */
function period() {
  const values = {};
  for (let year = 1991; year <= 2020; year += 1) values[year] = 26 + ((year % 5) - 2) * 0.5;
  return values;
}

describe("typical", () => {
  it("takes the year nearest the mean of the period, the later on a tie", () => {
    const values = { ...period(), 2063: 31.2 };
    const pick = typical(values, 1991, 2020);
    assert.equal(pick.mean, 26);
    assert.equal(values[pick.year], 26);
    assert.equal(pick.year, 2017);
  });

  it("never takes the year shown, and wants 20 years", () => {
    const values = period();
    assert.notEqual(typical(values, 1991, 2020, 2017).year, 2017);
    assert.equal(typical({ 2000: 25, 2001: 26 }, 1991, 2020), null);
  });

  it("goes to the end of the century from an observed season, back from a simulated one", () => {
    assert.deepEqual(typicalSpan(true), [2071, 2100]);
    assert.deepEqual(typicalSpan(false), [1991, 2020]);
  });
});

const KINDS = {
  epochs: [
    {
      id: "old", values: { 1985: 4.2, 1990: 7.5 },
      hottest: null, coldest: { year: 1985, date: "1986-01-06", value: -22.5 },
    },
    { id: "new", values: { 2030: 28.0 } },
    {
      id: "future", values: { 2063: 31.2, 2085: 33.1 },
      hottest: { year: 2063, date: "2063-08-04", value: 45.6 }, coldest: null,
    },
  ],
};

describe("allValues", () => {
  it("joins the years of every epoch", () => {
    assert.deepEqual(Object.keys(allValues(KINDS)).map(Number), [1985, 1990, 2030, 2063, 2085]);
    assert.deepEqual(allValues(null), {});
  });
});

describe("recordPick", () => {
  it("offers the hottest season of the future climate", () => {
    assert.deepEqual(recordPick(KINDS, "summer", 2030), { kind: "record", epoch: "future", year: 2085, day: null, value: 33.1 });
  });

  it("offers its hottest day when the record is on screen, nothing when that day is too", () => {
    assert.deepEqual(recordPick(KINDS, "summer", 2085, "record"), {
      kind: "hottestDay", epoch: "future", year: 2063, day: "2063-08-04", value: 45.6,
    });
    const sameYear = { epochs: [{ ...KINDS.epochs[2], hottest: { year: 2085, date: "2085-07-30", value: 44 } }] };
    assert.equal(recordPick(sameYear, "summer", 2085, "hottestDay"), null);
  });

  it("offers the coldest winter of the old climate in winter", () => {
    assert.equal(recordPick(KINDS, "winter", 2080).year, 1985);
    assert.equal(recordPick(KINDS, "winter", 2080).kind, "coldRecord");
    assert.equal(recordPick(KINDS, "winter", 1985).kind, "coldestDay");
  });

  it("is null without the epoch", () => {
    assert.equal(recordPick({ epochs: [] }, "summer", 2030), null);
  });
});

describe("recordWords", () => {
  it("names the record and its figure", () => {
    assert.deepEqual(recordWords({ kind: "record", epoch: "future", value: 33.1 }, "summer"), {
      kicker: "Record de chaleur du climat futur",
      line: "Maximales : 33,1 °C en moyenne",
    });
    assert.equal(recordWords({ kind: "coldestDay", epoch: "old", value: -22.5 }, "winter").line, "Minimale : -22,5 °C");
    assert.equal(recordWords({ kind: "coldRecord", epoch: "old", value: 4.2 }, "winter").kicker, "Record de froid de l'ancien climat");
  });

  it("writes the title of the block and the typical season", () => {
    assert.equal(texts.suggest.title, "À voir aussi");
    assert.equal(texts.suggest.typical("été", 1991, 2020), "Un été moyen de 1991-2020");
    assert.equal(degrees(26), "26,0 °C");
  });
});
