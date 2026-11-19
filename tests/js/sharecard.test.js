/**
 * The picture of the results page: its words, its tiles, its colours, and that
 * a simulated season says so on the picture itself.
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";

import {
  BANNERS, FORMATS, TILES, content, draw, fileName, fit, message, months, wrap,
} from "../../web/static/js/sharecard.js";

const SHEET = readFileSync(new URL("../../web/static/css/style.css", import.meta.url), "utf8");

/** A context that records what is written, text measured at half the font size per character. */
function recorder() {
  const texts = [];
  const gradient = { addColorStop() {} };
  const ctx = {
    font: "10px x",
    fillStyle: "",
    textAlign: "left",
    textBaseline: "alphabetic",
    measureText(text) {
      const size = Number(/(\d+)px/.exec(this.font)[1]);
      return { width: text.length * size * 0.5 };
    },
    fillText(text, x, y) {
      texts.push({ text, x, y, width: this.measureText(text).width, align: this.textAlign });
    },
    fillRect() {},
    createLinearGradient: () => gradient,
    beginPath() {}, moveTo() {}, arcTo() {}, closePath() {}, fill() {},
  };
  return { ctx, texts };
}

function days(start, n) {
  const first = new Date(`${start}T00:00:00Z`);
  return Array.from({ length: n }, (_, i) => {
    const d = new Date(first.getTime() + i * 86400000);
    return { date: d.toISOString().slice(0, 10), temperature_max_band: i % 10 };
  });
}

const PAGE = {
  title: "Été 2075 à Paris",
  rank: "Plus chaud que les 56 étés observés de 1970 à 2025.",
  figures: [
    { value: "+4,5 °C", label: "température maximale moyenne : 29,3 °C", normal: "normale 1991-2020 : 24,8 °C", tone: "warm" },
    { value: "13", label: "jours à 35 °C ou plus, dont 5 à 40 °C ou plus", normal: "normale 1991-2020 : 1,2", tone: "" },
    { value: "21", label: "nuits tropicales (minimale au-dessus de 20 °C)", normal: "normale 1991-2020 : 1,0", tone: "" },
    { value: "−19 %", label: "de pluie", normal: "normale", tone: "" },
  ],
  days: days("2075-06-21", 92),
  simulated: true,
  season: "summer",
  edges: [0, 5, 10, 15, 20, 25, 30, 35, 40],
  site: "Météo 2100",
  host: "meteo2100.example",
  notAForecast: "Simulation : une météo plausible, pas une prévision.",
};

describe("share card words", () => {
  it("wraps at spaces within the width", () => {
    const measure = (t) => t.length;
    assert.deepEqual(wrap("un deux trois quatre", 9, measure), ["un deux", "trois", "quatre"]);
    assert.deepEqual(wrap("anticonstitutionnellement", 5, measure), ["anticonstitutionnellement"]);
    assert.deepEqual(wrap("", 5, measure), []);
  });

  it("fits a title at the largest size that holds in two lines", () => {
    const at = (size) => (t) => t.length * size;
    const title = content(PAGE).title;
    assert.deepEqual(fit(title, 1000, [96, 60], 2, at), { size: 96, lines: ["Été 2075", "à\u00a0Paris"] });
    assert.equal(fit(title, 1000, [96, 60], 1, at).size, 60);
    const long = fit("Été 2075 à Saint-Martin-d'Hères-en-Vercors", 1000, [96, 84, 72, 60], 2, at);
    assert.ok(long.size < 60);
    assert.ok(long.lines.length <= 2);
    assert.ok(long.lines.every((line) => line.length * long.size <= 1000));
  });

  it("lays each month as the calendar: Monday to Sunday from left to right", () => {
    // 21 June 2075 is a Friday: the month starts at the row of its first day shown.
    const [june] = months(days("2075-06-21", 4));
    assert.equal(june.label, "juin");
    assert.deepEqual(june.tiles.map((t) => [t.column, t.row]), [[4, 0], [5, 0], [6, 0], [0, 1]]);
    assert.equal(june.rows, 2);
    // 1 August 2075 is a Thursday: a new month, under its weekday, on its first row.
    const turn = months(days("2075-07-30", 3));
    assert.deepEqual(turn.map((m) => m.label), ["juillet", "août"]);
    assert.deepEqual(turn[1].tiles.map((t) => [t.column, t.row]), [[3, 0]]);
    // Summer 2075: four months, the longest on five rows.
    const summer = months(days("2075-06-21", 92));
    assert.deepEqual(summer.map((m) => m.label), ["juin", "juillet", "août", "septembre"]);
    assert.deepEqual(summer.map((m) => m.rows), [2, 5, 5, 4]);
    assert.equal(months([{ date: "2075-06-23", temperature_max_band: null }])[0].tiles[0].band, null);
  });

  it("keeps three figures at most, the colon tied to the word before it", () => {
    assert.equal(content(PAGE).figures.length, 3);
    assert.equal(content(PAGE).figures[0].label, "température maximale moyenne\u00a0: 29,3\u00a0°C");
  });

  it("sends the caveat with a simulated season only", () => {
    const card = content(PAGE);
    assert.match(message(card), /pas une prévision/);
    assert.doesNotMatch(message(content({ ...PAGE, simulated: false })), /prévision/);
    assert.ok(message(card).startsWith("Été 2075 à\u00a0Paris. Plus chaud"));
  });

  it("names the file without accents or spaces", () => {
    assert.equal(fileName(content(PAGE).title, "square"), "meteo-2100-ete-2075-a-paris-carre.png");
    assert.equal(fileName("Hiver 2080-2081 à Grenoble", "story"), "meteo-2100-hiver-2080-2081-a-grenoble-story.png");
  });
});

describe("share card drawing", () => {
  for (const format of Object.keys(FORMATS)) {
    it(`writes the caveat and the site on a simulated ${format}, and no source`, () => {
      const { ctx, texts } = recorder();
      draw(ctx, content(PAGE), format);
      const written = texts.map((t) => t.text);
      assert.ok(written.includes(PAGE.notAForecast));
      assert.ok(!written.some((t) => /1991-2020|MPI-ESM1/.test(t)));
      assert.ok(!written.some((t) => /normale|Une case/.test(t)));
      assert.ok(written.includes("Météo 2100 · meteo2100.example"));
      assert.ok(written.includes("+4,5 °C"));
    });

    it(`keeps every word inside the ${format}`, () => {
      const { ctx, texts } = recorder();
      draw(ctx, content(PAGE), format);
      const { width, height } = FORMATS[format];
      for (const t of texts) {
        const left = t.align === "center" ? t.x - t.width / 2 : t.x;
        assert.ok(left >= 0 && left + t.width <= width, `${t.text} out of the width`);
        assert.ok(t.y > 0 && t.y <= height, `${t.text} out of the height`);
      }
    });
  }

  it("leaves the caveat off an observed season", () => {
    const { ctx, texts } = recorder();
    draw(ctx, content({ ...PAGE, simulated: false }), "square");
    assert.ok(!texts.some((t) => t.text === PAGE.notAForecast));
  });

  it("draws a card without summary", () => {
    const { ctx, texts } = recorder();
    draw(ctx, content({ ...PAGE, rank: "", figures: [] }), "square");
    assert.ok(texts.some((t) => t.text === "MÉTÉO 2100"));
  });
});

describe("share card colours", () => {
  it("are the calendar's tiles", () => {
    TILES.forEach((colour, band) => {
      const rule = new RegExp(`\\[data-band="${band}"\\] \\{ --tile: ${colour};`);
      assert.match(SHEET, rule, `band ${band}`);
    });
  });

  it("are the banners of the seasons", () => {
    for (const [season, { stops, ink }] of Object.entries(BANNERS)) {
      const block = new RegExp(`body\\.results\\[data-season="${season}"\\] \\{\\s*--banner: linear-gradient\\(([^;]+)\\);\\s*--banner-ink: (#[0-9a-f]+);`).exec(SHEET);
      assert.ok(block, season);
      assert.deepEqual(block[1].match(/#[0-9a-f]{6}/g), stops, season);
      assert.equal(block[2], ink, season);
    }
  });
});
