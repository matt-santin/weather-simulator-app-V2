/**
 * Raw value in, string ready to show out. No DOM, no state, no fetching.
 *
 * Everything that can be checked without a browser lives here, and `node --test`
 * is enough to check it. What is left elsewhere only places nodes.
 *
 * **Nothing here decides anything about the data.** The sky class arrives
 * decided by the server; the pictogram is picked from it, which is display and
 * display only — docs/application.md keeps the emoji off the JSON contract on
 * purpose, so that a drawn icon set would change this file and nothing else.
 *
 * The rounding is not a free choice either. docs/application.md settled it, and
 * the V1 CLAUDE.md rule 4 files rounding under data treatment: whole degrees, whole
 * km/h, **one decimal on millimetres**. That last one is the only one that is
 * not cosmetic — the 1 mm gate separates dry days from wet ones and commands
 * two of the five sky classes, so showing "0 mm" on a day carrying the rain
 * pictogram would be a contradiction on screen.
 */

import { texts } from "./i18n.js";

/** The five classes and the sixth case, which is the absence of one. */
export const SKY = {
  clear: { emoji: "☀️", label: texts.sky.clear },
  cloudy: { emoji: "⛅", label: texts.sky.cloudy },
  overcast: { emoji: "☁️", label: texts.sky.overcast },
  rain: { emoji: "🌧️", label: texts.sky.rain },
  snow: { emoji: "🌨️", label: texts.sky.snow },
};

/** No pictogram invented for a day the rule could not classify. */
const UNKNOWN_SKY = { emoji: "", label: texts.sky.unknown };

/**
 * The pictogram and its written equivalent, for any of the six cases.
 *
 * Both, always: an emoji alone is not readable by a screen reader, and
 * docs/application.md requires the written label beside it.
 */
export function sky(value) {
  return SKY[value] ?? UNKNOWN_SKY;
}

const WHOLE = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 });
const TENTH = new Intl.NumberFormat("fr-FR", {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

/**
 * The one test for a hole in the series.
 *
 * Both spellings, because both arrive: the JSON contract sends `null` for a day
 * a source left empty, and `undefined` is what an array reads back where the
 * normals have no such day at all. Every caller that draws or writes a
 * value asks here — `band.js` for the label it owes a missing number, `chart.js`
 * to break a curve rather than join across the hole — and it is exported for
 * that reason rather than kept private to the formatting below.
 */
export function isMissing(value) {
  return value === null || value === undefined;
}

/** A gap stays a gap. Filling it would be a data-treatment decision. */
function present(value, format) {
  return isMissing(value) ? texts.measure.missing : format.format(value);
}

export function temperature(value) {
  return present(value, WHOLE);
}

export function precipitation(value) {
  return present(value, TENTH);
}

export function wind(value) {
  return present(value, WHOLE);
}

/** Relative humidity, in whole percent. */
export function humidity(value) {
  return present(value, WHOLE);
}

// Dates arrive as "2046-07-14" and are read in UTC, deliberately. Left to the
// local zone, `new Date("2046-07-14")` lands on midnight UTC and slides back a
// day for any visitor west of Greenwich — the card would carry the wrong date
// while the server had it right.
// The numeric month rides on the day, and that is what lets the month line stay
// rare. A strip of ninety scrolls sideways, and a reader who scrolls past the
// turn used to lose the month with nothing to bring it back; naming it on every
// card fixed that and cost the turn its salience. Two digits after the day cost
// neither: the month is legible on any card, and the name written out still
// belongs to the day it changes.
const DAY = new Intl.DateTimeFormat("fr-FR", {
  weekday: "long",
  day: "2-digit",
  month: "2-digit",
  timeZone: "UTC",
});
const MONTH = new Intl.DateTimeFormat("fr-FR", { month: "long", timeZone: "UTC" });
const MONTH_YEAR = new Intl.DateTimeFormat("fr-FR", { month: "long", year: "numeric", timeZone: "UTC" });
const FULL = new Intl.DateTimeFormat("fr-FR", {
  day: "numeric",
  month: "long",
  year: "numeric",
  timeZone: "UTC",
});
const DAY_MONTH = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "long", timeZone: "UTC" });

/** "samedi 14/07" — what a card carries: the weekday spelled out, the date not. */
export function dayLabel(iso) {
  return DAY.format(new Date(iso));
}

/** "1", "14": the day of the month, under the weekday column of the calendar. */
export function dayOfMonth(iso) {
  return String(Number(iso.slice(8, 10)));
}

/** "juillet" — shown only where the month changes. */
export function monthLabel(iso) {
  return MONTH.format(new Date(iso));
}

/** "juillet 2046": the line that opens each month on the calendar. */
export function monthYear(iso) {
  return MONTH_YEAR.format(new Date(iso));
}

/** "14 juillet 2046" — the header, where there is room. */
export function fullDate(iso) {
  return FULL.format(new Date(iso));
}

/** "14 juillet": a date that recurs every year, in the matrix of years. */
export function dayMonth(iso) {
  return DAY_MONTH.format(new Date(iso));
}

/** "2046-07": what tells one month from the next, without parsing a date. */
export function monthKey(iso) {
  return iso.slice(0, 7);
}

/** The months a winter's snow is counted in, as on the server (thresholds.SNOW_SEASON_MONTHS). */
const SNOW_MONTHS = new Set(["11", "12", "01", "02", "03", "04"]);

/**
 * Snow on the ground over the days shown, in a sentence, from the `snow` of
 * /api/days: "Neige au sol 52 jours, dont 27 de suite du 2 au 28 février."
 * Empty where the server shows none, and for a range without snow that has no
 * day from November to April: a summer has nothing to be told about snow.
 */
export function snowCover(cover, days) {
  if (!cover) return "";
  if (cover.days === 0) {
    return days.some((day) => SNOW_MONTHS.has(day.date.slice(5, 7))) ? texts.snow.none : "";
  }
  const [from, to] = [cover.longest_start, cover.longest_end];
  // "du 2 au 28 février" within a month, "du 28 janvier au 19 février" across two.
  const first = from.slice(0, 7) === to.slice(0, 7) && from !== to ? dayOfMonth(from) : dayMonth(from);
  return texts.snow.cover(cover.days, cover.longest_days, first, dayMonth(to));
}

/**
 * The driest day of the range for the soil, in a sentence: "Eau du sol au plus
 * bas : 6 % de la réserve utile, le 28 juillet." The first of two equal days.
 * Empty where no day carries a value.
 */
export function soilLow(days) {
  let low = null;
  for (const day of days) {
    if (isMissing(day.soil_water)) continue;
    if (low === null || day.soil_water < low.soil_water) low = day;
  }
  return low === null ? "" : texts.soil.lowest(low.soil_water, dayMonth(low.date));
}

/**
 * A sentence, cut where a footnote call belongs in it.
 *
 * French typography puts the call *before* the full stop — « N'importe quand*. »
 * and not « N'importe quand.* » — so the mark cannot simply follow the sentence
 * the way an appended node would. This says where to cut, and the dictionary
 * keeps its sentence whole: no key ends in a half-phrase, and nothing has to be
 * reassembled by a translator.
 *
 * **The whole trailing run, not one character.** An ellipsis is three marks and
 * « … ?! » is more; a call goes before the lot, not inside it. A sentence
 * ending in none — which no French sentence does, but a key might while it is
 * being written — comes back whole with an empty tail, and the mark lands at the
 * end, which is the only sensible place left.
 */
export function beforeFinalPunctuation(sentence) {
  const tail = /[.!?…]+$/.exec(sentence);
  const cut = tail ? tail.index : sentence.length;
  return { body: sentence.slice(0, cut), tail: sentence.slice(cut) };
}
