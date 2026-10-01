/**
 * What the interface shows, checked without a browser.
 *
 * `node --test`, no dependency, no install, no build step. Everything testable
 * this way was deliberately put in present.js; what is left only places nodes.
 *
 * The last suite is the one that matters most. CLAUDE.md rule 1 outranks
 * everything else in this project and forbids the vocabulary of forecasting on
 * a future date — until now that was a sentence in a document, which is to say
 * something a hurried edit walks straight past. Here it fails a test.
 */

import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { describe, it } from "node:test";
import { fileURLToPath } from "node:url";

import { texts } from "../../web/static/js/i18n.js";
import * as present from "../../web/static/js/present.js";

describe("the sky class", () => {
  // Reproduced from docs/application.md, on purpose rather than imported: the
  // point is to fail when the code and the document disagree.
  const DOCUMENTED = [
    ["clear", "☀️", "Dégagé"],
    ["cloudy", "⛅", "Nuageux"],
    ["overcast", "☁️", "Couvert"],
    ["rain", "🌧️", "Pluie"],
    ["snow", "🌨️", "Neige"],
  ];

  for (const [value, emoji, label] of DOCUMENTED) {
    it(`${value} shows ${emoji} and "${label}"`, () => {
      assert.deepEqual(present.sky(value), { emoji, label });
    });
  }

  it("the five classes, and nothing more", () => {
    assert.deepEqual(
      Object.keys(present.SKY),
      DOCUMENTED.map(([value]) => value),
    );
  });

  it("a day with no class gets a label, never an invented pictogram", () => {
    const absent = { emoji: "", label: "Ciel indéterminé" };
    assert.deepEqual(present.sky(null), absent);
    assert.deepEqual(present.sky(undefined), absent);
    // A class the server has never served must not fall through to a picture.
    assert.deepEqual(present.sky("fog"), absent);
  });
});

describe("the display rounding", () => {
  // Settled in docs/application.md and validated: whole degrees, whole km/h,
  // one decimal on millimetres. The last is the only one that is not cosmetic.
  it("temperatures as whole numbers", () => {
    assert.equal(present.temperature(21.34), "21");
    assert.equal(present.temperature(38.9), "39");
    assert.equal(present.temperature(-3.2), "-3");
  });

  it("winds as whole numbers", () => {
    assert.equal(present.wind(8.4), "8");
    assert.equal(present.wind(18.7), "19");
  });

  it("precipitation to a tenth, with a French decimal comma", () => {
    assert.equal(present.precipitation(0.44), "0,4");
    assert.equal(present.precipitation(1.24), "1,2");
    assert.equal(present.precipitation(12), "12,0");
  });

  it("the tenth tells a dry day from a wet one", () => {
    // The 1 mm gate commands two of the five sky classes. Showing "0 mm" on a
    // day carrying the rain pictogram would be a contradiction on screen.
    assert.notEqual(present.precipitation(0.4), present.precipitation(1.2));
  });
});

describe("the gaps", () => {
  it("a missing measure shows a dash, never NaN or undefined", () => {
    for (const format of [present.temperature, present.precipitation, present.wind]) {
      for (const gap of [null, undefined]) {
        assert.equal(format(gap), "—");
      }
    }
  });

  it("isMissing does not take zero for an absence", () => {
    assert.equal(present.isMissing(0), false);
    assert.equal(present.precipitation(0), "0,0");
    assert.equal(present.isMissing(null), true);
  });
});

describe("the dates", () => {
  it("carry the day, the month and the year in French", () => {
    assert.equal(present.dayLabel("2046-07-14"), "samedi 14/07");
    assert.equal(present.monthLabel("2046-07-14"), "juillet");
    assert.equal(present.fullDate("2046-07-14"), "14 juillet 2046");
  });

  it("are read in UTC, wherever the visitor is", () => {
    // Left to the local zone, "2046-07-14" lands on midnight UTC and slides
    // back a day west of Greenwich — the card would carry the 13th while the
    // server had the 14th. A fresh process is the only way to prove it: the
    // zone is fixed when this one starts.
    const west = execFileSync(
      process.execPath,
      [
        "--input-type=module",
        "-e",
        "const m = await import('./web/static/js/present.js');" +
          "console.log(m.dayLabel('2046-07-14'), '|', m.fullDate('2046-07-14'));",
      ],
      {
        cwd: fileURLToPath(new URL("../..", import.meta.url)),
        env: { ...process.env, TZ: "America/Los_Angeles" },
        encoding: "utf8",
      },
    ).trim();
    assert.equal(west, "samedi 14/07 | 14 juillet 2046");
  });

  it("the month marker turns on the month, not on the day", () => {
    assert.equal(present.monthKey("2046-07-14"), present.monthKey("2046-07-31"));
    assert.notEqual(present.monthKey("2046-07-31"), present.monthKey("2046-08-01"));
  });
});

describe("the vocabulary, rule 1", () => {
  const FORBIDDEN = ["prévision", "prévisions", "il fera"];

  // The sentences whose whole job is to place the word correctly: each names
  // the forecast in order to say that this is not one. Widening this list is
  // the moment to stop and think, which is why it is written out.
  const ALLOWED = ["warning.note", "warning.noteMeaning", "warning.notAForecast"];

  /** Every string in the dictionary, including those a function returns. */
  function* strings(node, path = "") {
    if (typeof node === "string") {
      yield [path, node];
    } else if (typeof node === "function") {
      yield [path, String(node("…", "…"))];
    } else if (node && typeof node === "object") {
      for (const [key, child] of Object.entries(node)) {
        yield* strings(child, path ? `${path}.${key}` : key);
      }
    }
  }

  it("no string speaks of a forecast, but those written to deny one", () => {
    for (const [path, text] of strings(texts)) {
      if (ALLOWED.includes(path)) continue;
      for (const word of FORBIDDEN) {
        assert.ok(!text.toLowerCase().includes(word), `"${word}" in texts.${path}: ${text}`);
      }
    }
  });

  it("and the warning does deny it", () => {
    assert.match(texts.warning.notAForecast, /prévision/);
  });

  it("the wind is never a gust", () => {
    // The daily mean wind; a gust commonly runs to several times it.
    for (const [path, text] of strings(texts)) {
      assert.ok(!text.toLowerCase().includes("rafale"), `"rafale" in texts.${path}`);
    }
  });
});

/**
 * Where a footnote call goes in a sentence.
 *
 * French typography puts it before the full stop, so the promise on the accueil
 * has to be cut rather than followed. The cut is arithmetic on a string, which
 * is why it lives here and not in `home.js` with the node that carries it.
 */
describe("the footnote call", () => {
  it("goes before the full stop, not after it", () => {
    assert.deepEqual(present.beforeFinalPunctuation("N'importe quand."), {
      body: "N'importe quand",
      tail: ".",
    });
  });

  it("goes before the whole run, not into the middle of it", () => {
    // An ellipsis is three marks and "… ?" is more. A call belongs ahead of the
    // lot; splitting one would put a star inside the punctuation.
    assert.equal(present.beforeFinalPunctuation("Vraiment…").tail, "…");
    assert.equal(present.beforeFinalPunctuation("Vraiment...").tail, "...");
    assert.equal(present.beforeFinalPunctuation("Vraiment ?!").tail, "?!");
  });

  it("leaves a sentence with no punctuation whole", () => {
    // No French sentence ends this way, but a key being written might. The mark
    // then lands at the end, which is the only place left.
    assert.deepEqual(present.beforeFinalPunctuation("Sans point"), {
      body: "Sans point",
      tail: "",
    });
  });

  it("cuts the promise the accueil actually carries", () => {
    // The one that matters: the dictionary keeps its sentences whole, and this
    // is what the page makes of the last of them — the line the call sits on.
    const last = texts.home.promise.split("\n").at(-1);
    const { body, tail } = present.beforeFinalPunctuation(last);
    assert.equal(body + tail, last);
    assert.equal(tail, ".");
    assert.ok(body.endsWith("N'importe quand"));
  });
});

/**
 * Where the promise breaks.
 *
 * The accueil sets it on three lines, and that is composition rather than
 * wrapping: a width narrow enough to force them breaks wherever the font runs
 * out, and the font is not a given — Georgia stands in until EB Garamond
 * arrives, and sets the same sentence to a different length. So the breaks are
 * written into the string, and what is checked here is that the string stays
 * something `home.js` can set: lines with words in them, and a last line the
 * footnote call can be cut into.
 */
describe("the lines of the promise", () => {
  const lines = texts.home.promise.split("\n");

  it("carries its own breaks", () => {
    assert.ok(lines.length > 1, "la promesse tient sur une seule ligne");
  });

  it("has no empty line", () => {
    // A trailing "\n", or two in a row, would set a blank line under the
    // promise and push the form down by one — silently, since nothing else
    // reads this string.
    assert.deepEqual(lines.filter((line) => line.trim() === ""), []);
  });

  it("loses nothing but the breaks it was written with", () => {
    assert.equal(lines.join("\n"), texts.home.promise);
  });
});
