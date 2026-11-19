/**
 * The picture a visitor takes away from the results page (18/11/2026): drawn in
 * the browser, on a canvas, from what the page already shows. No fetching; the
 * drawing takes any object with the methods of a 2D context it uses, so that
 * `node --test` checks it with a recording stub.
 *
 * Two formats: a square (1080 × 1080, a post) and a story (1080 × 1920). In
 * bands across the width: the season's band with the name of the site and the
 * title; the rank sentence; three figures of the summary side by side (value
 * over words, without their normals: the page gives them); one small calendar
 * per month, side by side (four to a row in the square, two in the story), one
 * tile per day in the colour of its maximum, Monday to Sunday from left to
 * right as on the page, with the scale; the foot.
 *
 * **The foot always says what the picture is.** A picture travels without its
 * page: a simulated season carries "Simulation : une météo plausible, pas une
 * prévision." on the picture itself, and every picture carries the address of
 * the site.
 */

export const FORMATS = {
  square: { width: 1080, height: 1080 },
  story: { width: 1080, height: 1920 },
};

// The ten colours of the calendar's tiles, band 0 first (style.css, data-band;
// the same list as TILES in src/app/api/share.py). A test holds them equal.
export const TILES = ["#2b59c3", "#5c95e8", "#62c6c4", "#9fd77f", "#f7e15f",
  "#fdb342", "#f26b38", "#c81d25", "#5a0b2f", "#1a1a1a"];
const GAP_TILE = "#d5d9e0";

// The banner of each season (style.css, body.results[data-season]): its stops
// and its ink. A test holds them equal to the sheet.
export const BANNERS = {
  winter: { stops: ["#dbeaf7", "#b3d0e8", "#8fb6dc", "#6f9dc9"], ink: "#0b1c30" },
  spring: { stops: ["#eaf3c8", "#d8e894", "#c8d94a", "#a9c23c"], ink: "#17280c" },
  summer: { stops: ["#fbbe7f", "#fe9e52", "#ff7b30", "#fd5816", "#fd3a0c"], ink: "#21100a" },
  autumn: { stops: ["#fae2bd", "#f3bb72", "#e08a35", "#d07a2c"], ink: "#2a1206" },
};

const GROUND = "#f4f6f9";
const INK = "#14202e";
const SOFT = "#4a5768"; // 7,4:1 on the ground
const WARM = "#c2410c";
const COOL = "#1d5fb4";
const SERIF = '"EB Garamond", Georgia, serif';
const SANS = 'Inter, system-ui, sans-serif';

/** The fonts the drawing uses, to be loaded before it (document.fonts.load). */
export const FONTS = [`500 80px ${SERIF}`, `italic 400 40px ${SERIF}`, `400 24px ${SANS}`, `600 24px ${SANS}`];

/**
 * ``text`` cut into lines no wider than ``width``, at spaces, by ``measure``
 * (text -> width). A word wider than the line stands alone on its line.
 */
export function wrap(text, width, measure) {
  const lines = [];
  let line = "";
  for (const word of String(text).split(/ +/).filter(Boolean)) {
    const next = line ? `${line} ${word}` : word;
    if (line && measure(next) > width) {
      lines.push(line);
      line = word;
    } else {
      line = next;
    }
  }
  if (line) lines.push(line);
  return lines;
}

/**
 * The largest of ``sizes`` (descending) at which ``text`` holds in ``maxLines``
 * lines no wider than ``width``; ``measureAt(size)`` gives the measure at that
 * size. When none holds (a very long name), the smallest size, brought down
 * further until its widest line fits, cut to ``maxLines``.
 */
export function fit(text, width, sizes, maxLines, measureAt) {
  const holds = (lines, measure) => lines.length <= maxLines && lines.every((l) => measure(l) <= width);
  for (const size of sizes) {
    const measure = measureAt(size);
    const lines = wrap(text, width, measure);
    if (holds(lines, measure)) return { size, lines };
  }
  const smallest = sizes[sizes.length - 1];
  const measure = measureAt(smallest);
  const lines = wrap(text, width, measure).slice(0, maxLines);
  const widest = Math.max(...lines.map(measure), 1);
  return { size: Math.min(smallest, Math.floor((smallest * width) / widest)), lines };
}

const MONTH = new Intl.DateTimeFormat("fr-FR", { month: "long", timeZone: "UTC" });

/**
 * The days as small calendars, one per month: ``[{ label, rows, tiles }]``,
 * each tile ``{ column, row, band }``, seven columns from Monday to Sunday read
 * from left to right, a row per week of the month, as the calendar of the
 * page; a month cut by the dates starts at the row of its first day shown.
 * ``band`` null for a day without value.
 */
export function months(days) {
  const out = [];
  let shownFrom = 0;
  for (const day of days) {
    const date = new Date(`${day.date}T00:00:00Z`);
    const key = day.date.slice(0, 7);
    const first = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), 1));
    const offset = (first.getUTCDay() + 6) % 7; // weekday of the 1st, Monday 0
    const fullRow = Math.floor((date.getUTCDate() - 1 + offset) / 7);
    if (!out.length || out[out.length - 1].key !== key) {
      out.push({ key, label: MONTH.format(date), rows: 0, tiles: [] });
      shownFrom = fullRow;
    }
    const month = out[out.length - 1];
    const row = fullRow - shownFrom;
    month.tiles.push({ column: (date.getUTCDay() + 6) % 7, row, band: day.temperature_max_band ?? null });
    month.rows = Math.max(month.rows, row + 1);
  }
  return out.map(({ label, rows, tiles }) => ({ label, rows, tiles }));
}

/**
 * What the picture says, from what the page holds: ``title`` ("Été 2075 à
 * Paris"), ``rank`` (the sentence, or ""), ``figures`` (summary.js, three at
 * most, their value and label only), ``days`` (/api/days), ``simulated``,
 * ``season``, ``edges`` (the bounds of the tiles' bands, /api/config), ``site``
 * and ``host``.
 */
export function content(page) {
  return {
    // "à" kept with the place: a line of the title never ends on it.
    title: String(page.title).replace(/ à /g, " à "),
    rank: page.rank ?? "",
    // The colon kept with the word before it: a line never starts on it.
    figures: (page.figures ?? []).slice(0, 3).map(({ value, label, tone }) => ({
      value,
      label: label.replace(/ ([:;!?])/g, " $1"),
      tone,
    })),
    months: months(page.days ?? []),
    simulated: Boolean(page.simulated),
    banner: BANNERS[page.season] ?? BANNERS.summer,
    edges: page.edges ?? [],
    site: page.site,
    host: page.host ?? "",
    notAForecast: page.notAForecast,
  };
}

/** Draw ``card`` (``content``) on ``ctx`` in ``format`` (a key of FORMATS). */
export function draw(ctx, card, format = "square") {
  const { width, height } = FORMATS[format];
  const story = format === "story";
  const k = story ? 1.2 : 1; // the story's type, a little larger
  const margin = 72;
  const inner = width - 2 * margin;
  const at = (weight, size, family) => (text) => {
    ctx.font = `${weight} ${size}px ${family}`;
    return ctx.measureText(text).width;
  };

  ctx.fillStyle = GROUND;
  ctx.fillRect(0, 0, width, height);

  // The band of the season: the site's name, then the title, on one line when
  // it holds at 60 px or more, on two otherwise.
  const sizes = [96, 84, 72, 60].map((s) => Math.round(s * k));
  const measureTitle = (size) => at(500, size, SERIF);
  const single = fit(card.title, inner, sizes, 1, measureTitle);
  const title = single.size >= sizes[sizes.length - 1] && wrap(card.title, inner, measureTitle(single.size)).length === 1
    ? single
    : fit(card.title, inner, sizes, 2, measureTitle);
  const titleLead = Math.round(title.size * 1.08);
  const brandSize = Math.round(26 * k);
  const bandTop = story ? 160 : 56;
  const bandHeight = bandTop + brandSize + 36 + titleLead * title.lines.length + (story ? 56 : 44);
  const gradient = ctx.createLinearGradient(0, 0, 0, bandHeight);
  card.banner.stops.forEach((stop, i) => gradient.addColorStop(i / (card.banner.stops.length - 1), stop));
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, width, bandHeight);
  // The filet of the temperature scale under the band, as on the page.
  const filet = ctx.createLinearGradient(0, 0, width, 0);
  ["#2b59c3", "#62c6c4", "#f7e15f", "#fdb342", "#f26b38", "#c81d25"].forEach((c, i, all) =>
    filet.addColorStop(i / (all.length - 1), c));
  ctx.fillStyle = filet;
  ctx.fillRect(0, bandHeight - 6, width, 6);

  ctx.textBaseline = "alphabetic";
  ctx.textAlign = "left";
  ctx.fillStyle = card.banner.ink;
  ctx.font = `600 ${brandSize}px ${SANS}`;
  let y = bandTop + brandSize;
  ctx.fillText(card.site.toUpperCase(), margin, y);
  ctx.font = `500 ${title.size}px ${SERIF}`;
  y += 36;
  for (const line of title.lines) {
    y += titleLead;
    ctx.fillText(line, margin, y - Math.round(title.size * 0.2));
  }

  // Under the band, in bands across the width: the rank sentence, the
  // figures side by side, the months side by side, the foot. What is left of
  // the height goes, in equal parts, between them.
  const rank = layRank(card, inner, k, at);
  const figures = layFigures(card, inner, k, at);
  const footSize = Math.round(22 * k);
  const footLead = Math.round(footSize * 1.5);
  const footLines = [card.simulated ? card.notAForecast : "", card.host ? `${card.site} · ${card.host}` : card.site]
    .filter(Boolean);
  const footHeight = (footLines.length - 1) * footLead + footSize;
  const top = bandHeight + Math.round(44 * k);
  const last = height - (story ? 140 : 52); // the baseline of the foot's last line
  const parts = [rank.height, figures.height].filter(Boolean);
  const minGap = Math.round(36 * k);
  const room = last - footHeight - top - parts.reduce((a, b) => a + b, 0) - minGap * (parts.length + 1);
  const calendar = layCalendar(card, inner, room, k, story);
  const used = parts.reduce((a, b) => a + b, 0) + (calendar ? calendar.height : 0);
  const blocks = parts.length + (calendar ? 1 : 0);
  const gap = Math.min(Math.max((last - footHeight - top - used) / blocks, minGap), 110 * k);

  y = top;
  if (rank.height) {
    drawRank(ctx, rank, margin, y);
    y += rank.height + gap;
  }
  if (figures.height) {
    drawFigures(ctx, figures, margin, y);
    y += figures.height + gap;
  }
  if (calendar) drawCalendar(ctx, card, calendar, margin, y, inner, k);

  ctx.font = `600 ${footSize}px ${SANS}`;
  ctx.fillStyle = INK;
  footLines.forEach((line, i) => ctx.fillText(line, margin, last - (footLines.length - 1 - i) * footLead));
}

/** The rank sentence across the width: ``{ size, lines, height }``. */
function layRank(card, width, k, at) {
  const size = Math.round(40 * k);
  const lines = card.rank ? wrap(card.rank, width, at("italic 400", size, SERIF)).slice(0, 3) : [];
  return { size, lines, height: lines.length ? Math.round(size * (lines.length * 1.25 - 0.25)) : 0 };
}

function drawRank(ctx, rank, x, y) {
  ctx.fillStyle = INK;
  ctx.font = `italic 400 ${rank.size}px ${SERIF}`;
  rank.lines.forEach((line, i) => ctx.fillText(line, x, y + rank.size * 0.8 + i * Math.round(rank.size * 1.25)));
}

/**
 * The figures side by side, each in a column of its own: the value, its words
 * under it, all on the same left edge.
 */
function layFigures(card, width, k, at) {
  if (!card.figures.length) return { height: 0 };
  const gutter = 40;
  const column = (width - gutter * (card.figures.length - 1)) / card.figures.length;
  const valueSize = Math.round(68 * k);
  const labelSize = Math.round(22 * k);
  const lead = Math.round(labelSize * 1.3);
  const measure = at(400, labelSize, SANS);
  const columns = card.figures.map((figure) => ({ figure, lines: wrap(figure.label, column, measure).slice(0, 3) }));
  const most = Math.max(...columns.map((c) => c.lines.length));
  const gapUnder = Math.round(12 * k);
  return { columns, column, gutter, valueSize, labelSize, lead, gapUnder, height: valueSize + gapUnder + most * lead };
}

function drawFigures(ctx, lay, x, y) {
  lay.columns.forEach(({ figure, lines }, i) => {
    const left = x + i * (lay.column + lay.gutter);
    ctx.fillStyle = figure.tone === "warm" ? WARM : figure.tone === "cool" ? COOL : INK;
    ctx.font = `500 ${lay.valueSize}px ${SERIF}`;
    ctx.fillText(figure.value, left, y + lay.valueSize * 0.78);
    ctx.fillStyle = INK;
    ctx.font = `400 ${lay.labelSize}px ${SANS}`;
    lines.forEach((line, j) => ctx.fillText(line, left, y + lay.valueSize + lay.gapUnder + lay.labelSize + j * lay.lead));
  });
}

/**
 * The months side by side (four to a row in the square, two in the story),
 * in ``room`` of height: ``{ step, perRow, lines, label, header, scale, height }``;
 * null without days.
 */
function layCalendar(card, width, room, k, story) {
  if (!card.months.length) return null;
  const perRow = Math.min(card.months.length, story ? 2 : 4);
  const lines = [];
  for (let i = 0; i < card.months.length; i += perRow) lines.push(card.months.slice(i, i + perRow));
  const label = Math.round(30 * k); // the month's name
  const header = Math.round(26 * k); // the weekdays
  const scale = card.edges.length ? Math.round(64 * k) : 0;
  const between = 0.9; // the gap between two months, in steps
  const rows = lines.reduce((sum, line) => sum + Math.max(...line.map((m) => m.rows)), 0);
  const fixed = lines.length * (label + header) + (lines.length - 1) * Math.round(24 * k) + scale;
  const step = Math.floor(Math.min(width / (perRow * 7 + (perRow - 1) * between), (room - fixed) / rows, 72 * k));
  if (step < 6) return null;
  return { step, perRow, lines, label, header, scale, between, height: fixed + rows * step };
}

const WEEKDAYS = ["L", "M", "M", "J", "V", "S", "D"];

function drawCalendar(ctx, card, cal, x, y, width, k) {
  const { step } = cal;
  const size = Math.round(step * 0.88);
  const block = step * 7;
  const lineWidth = (n) => n * block + (n - 1) * step * cal.between;
  for (const line of cal.lines) {
    const left = x + (width - lineWidth(line.length)) / 2;
    line.forEach((month, i) => {
      const mx = left + i * (block + step * cal.between);
      ctx.textAlign = "left";
      ctx.fillStyle = INK;
      ctx.font = `600 ${Math.round(20 * k)}px ${SANS}`;
      ctx.fillText(month.label, mx, y + Math.round(20 * k));
      ctx.textAlign = "center";
      ctx.fillStyle = SOFT;
      ctx.font = `600 ${Math.round(14 * k)}px ${SANS}`;
      WEEKDAYS.forEach((day, d) => ctx.fillText(day, mx + d * step + size / 2, y + cal.label + Math.round(14 * k)));
      const grid = y + cal.label + cal.header;
      for (const tile of month.tiles) {
        ctx.fillStyle = tile.band === null ? GAP_TILE : TILES[tile.band] ?? GAP_TILE;
        roundRect(ctx, mx + tile.column * step, grid + tile.row * step, size, size, Math.round(size * 0.16));
      }
    });
    y += cal.label + cal.header + Math.max(...line.map((m) => m.rows)) * step + Math.round(24 * k);
  }
  ctx.textAlign = "left";
  if (!cal.scale) return;
  // The scale, centred: one chip per band, the bounds every 10 °C.
  const chip = Math.min(56 * k, width / TILES.length);
  const left = x + (width - chip * TILES.length) / 2;
  const top = y - Math.round(24 * k) + Math.round(22 * k);
  const chipHeight = Math.round(12 * k);
  TILES.forEach((color, i) => {
    ctx.fillStyle = color;
    ctx.fillRect(left + i * chip, top, chip, chipHeight);
  });
  const scaleSize = Math.round(17 * k);
  ctx.font = `400 ${scaleSize}px ${SANS}`;
  ctx.fillStyle = SOFT;
  ctx.textAlign = "center";
  const base = top + chipHeight + scaleSize + 6;
  card.edges.forEach((edge, i) => {
    if (i % 2 === 0 && i < card.edges.length - 1) ctx.fillText(`${edge}`, left + (i + 1) * chip, base);
  });
  ctx.fillText(`${card.edges[card.edges.length - 1]} °C`, left + card.edges.length * chip, base);
  ctx.textAlign = "left";
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
  ctx.fill();
}

/**
 * The words sent with a shared link: the title and the rank sentence, and the
 * caveat for a simulated season.
 */
export function message(card) {
  return [card.title + ".", card.rank, card.simulated ? card.notAForecast : ""].filter(Boolean).join(" ");
}

/** The file name of the picture: "meteo-2100-ete-2075-paris-carre.png". */
export function fileName(title, format) {
  const slug = `météo 2100 ${title}`
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
  return `${slug}-${format === "story" ? "story" : "carre"}.png`;
}
