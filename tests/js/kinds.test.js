/**
 * The kind mode of the home form: the words of the three kinds, the year the
 * server is asked about, and the draw.
 */

import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { KINDS, anyYearOf, draw, epochLabel, kindLabels } from "../../web/static/js/kinds.js";
import { texts } from "../../web/static/js/i18n.js";

describe("kindLabels", () => {
  it("names every kind, a winter cold or mild", () => {
    for (const season of Object.keys(texts.season)) {
      const labels = kindLabels(season);
      assert.deepEqual(Object.keys(labels).sort(), [...KINDS].sort());
    }
    assert.equal(kindLabels("winter").warm, "Doux");
    assert.equal(kindLabels("summer").warm, "Chaud");
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

  it("answers null when there is none", () => {
    assert.equal(draw({ cool: [] }, "cool"), null);
    assert.equal(draw(undefined, "warm"), null);
  });
});
