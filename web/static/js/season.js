/**
 * Seasons, read both ways: which one a search falls in, and which dates one is.
 *
 * No DOM, no state, no fetching — the neighbour of `present.js` and `bounds.js`,
 * and `node --test` is enough to check it.
 *
 * **One table, two readings, and that is the whole design of this file.**
 * `seasonOf` turns a date into a season so the results page can be put on its
 * ground; `rangeOf` turns a season into two dates so the form can ask for one by
 * name. Writing "21 June to 20 September" a second time for the second reading
 * is exactly the duplication CLAUDE.md rule 3 is about, and the rule does not
 * care that both copies would sit in the same file — five obvious lines diverge
 * as surely as a clever one, and less visibly. So the boundaries are declared
 * once, in `SEASONS`, and both directions walk it.
 *
 * **This is not a duplicated rule.** The server holds no version of the season:
 * it is derived here from `debut` and `fin`, which the URL already carries, and
 * it decides a background and nothing else. CLAUDE.md rule 3 sends that to the
 * browser — the criterion is the second copy, and there is no first one.
 *
 * **Astronomical bounds, not meteorological ones.** 21 December to 20 March, and
 * so on: the dates the visitor was asked about. They shift by a day from one year
 * to the next in the sky and do not here, which is the right trade for a wash of
 * colour — a page whose ground moved on 20 March one year and 21 March the next
 * would be answering a question nobody asked.
 *
 * **Reversed below the equator.** The latitude travels in the URL beside the
 * dates, and January in Santiago is a summer — a white-to-navy page under 30 °C
 * would be a picture of the calendar rather than of the weather the range holds.
 */

import { eachDay, pad } from "./calendar.js";

/** Winter first, and it is the one that wraps: December belongs to January's. */
const OPPOSITE = {
  winter: "summer",
  spring: "autumn",
  summer: "winter",
  autumn: "spring",
};

/**
 * The four northern seasons and the day each one opens on.
 *
 * **In calendar order, spring first**, which is not a matter of taste: the list
 * is walked forwards to find which season a date has reached, and forwards again
 * to find where a season ends — the next entry's eve, wrapping at the end. Both
 * walks want the same order, and winter last is what makes it the one that owns
 * everything before the first boundary. December and January are one season and
 * the table says so by its shape rather than by a special case.
 *
 * **Every boundary falls on the 21st**, and `rangeOf` leans on it: the eve of the
 * 21st is the 20th of the same month, so a season's last day needs no date
 * arithmetic and no timezone. Move a boundary to the 1st and that stops holding
 * — a test guards it.
 */
const SEASONS = [
  { name: "spring", from: [3, 21] },
  { name: "summer", from: [6, 21] },
  { name: "autumn", from: [9, 21] },
  { name: "winter", from: [12, 21] },
];

/** A month and a day as one comparable number: 21 June is 621. */
const stampOf = ([month, day]) => month * 100 + day;

/**
 * The northern season of a month and a day, read as one number.
 *
 * `month * 100 + day` orders dates inside a year without parsing one, in the
 * same spirit as `bounds.js` comparing ISO strings: nothing here can slide a day
 * by reading it in the wrong zone, because nothing here reads a zone. Both sides
 * of the comparison go through `stampOf`, the date being read and the boundary
 * alike — written out here it would be the same expression twice, two lines
 * apart, which is the shape this file's own header argues against.
 *
 * The walk starts on the last entry — winter — because a date before the first
 * boundary is in the season that began in the year before.
 */
function northern(month, day) {
  const stamp = stampOf([month, day]);
  let found = SEASONS.at(-1);
  for (const season of SEASONS) {
    if (stamp >= stampOf(season.from)) found = season;
  }
  return found.name;
}

/**
 * The season one day belongs to. `iso` is "2046-07-14".
 *
 * The hemisphere is settled here rather than in the count below, so that
 * counting has nothing to know about it. A missing or unreadable latitude
 * compares false against zero and lands on the northern reading, which is what a
 * hand-edited URL should get: the calendar, not an error.
 */
export function seasonOf(iso, latitude) {
  const season = northern(Number(iso.slice(5, 7)), Number(iso.slice(8, 10)));
  return latitude < 0 ? OPPOSITE[season] : season;
}

/**
 * The dates one season covers, as `{ start, end }`, or null if it has no name.
 *
 * The other reading of `SEASONS`, and the exact inverse of `seasonOf`: feed the
 * range this returns back through it and the season comes out again, on either
 * hemisphere. That round trip is what keeps the season the form asked for and
 * the season the results page paints from ever disagreeing — they are two walks
 * of one table, not two rules that happen to match.
 *
 * **`year` is the year the season opens in**, for all four alike. Winter is the
 * only one that lands in two calendar years, and "hiver 2029" is read here as
 * the winter that begins in December 2029 — a uniform rule rather than the one
 * French usage leaves ambiguous. `yearsFor` is what keeps a visitor from being
 * offered one whose far end falls outside the covered period.
 *
 * **Below the equator the season asked for is the place's, not the calendar's.**
 * "Été" in Santiago is 21 December to 20 March. The request is turned into its
 * northern equivalent before the table is read, which is the same hop `seasonOf`
 * makes in the other direction — hence the round trip.
 */
export function rangeOf(name, year, latitude) {
  const wanted = latitude < 0 ? OPPOSITE[name] : name;
  const index = SEASONS.findIndex((season) => season.name === wanted);
  if (index < 0 || !Number.isInteger(year)) return null;

  const [month, day] = SEASONS[index].from;
  const [nextMonth, nextDay] = SEASONS[(index + 1) % SEASONS.length].from;
  // The next season's eve. Every boundary being the 21st, that is the 20th of
  // the same month: no day to borrow, no month to carry, no zone to read.
  const wraps = nextMonth < month;
  return {
    start: `${year}-${pad(month)}-${pad(day)}`,
    end: `${wraps ? year + 1 : year}-${pad(nextMonth)}-${pad(nextDay - 1)}`,
  };
}

/**
 * The years this season can be asked for, given what the API says it covers.
 *
 * `config` is what `/api/config` served — the bounds are read from it and never
 * written here, for the reason `bounds.js` gives at length. ISO strings compare
 * correctly, so the test is a string comparison and nothing is parsed.
 *
 * In practice this only ever removes winters: a northern winter 2050 would end
 * on 20 March 2051, past the last day the model reaches, and offering it would
 * be offering a refusal. Below the equator it is summer that loses the year, the
 * two being the same three months.
 */
export function yearsFor(name, latitude, config) {
  const years = [];
  const first = Math.min(...config.periods.map((p) => Number(p.start.slice(0, 4))));
  const last = Math.max(...config.periods.map((p) => Number(p.end.slice(0, 4))));
  for (let year = first; year <= last; year += 1) {
    const range = rangeOf(name, year, latitude);
    if (range && config.periods.some((p) => range.start >= p.start && range.end <= p.end)) {
      years.push(year);
    }
  }
  return years;
}

/**
 * The season the range spends most of its days in, or null if there is no range.
 *
 * **It counts days, and nothing else, which is why the bound moving cost it
 * nothing.** At ninety days a range could touch two seasons at most — winter,
 * the shortest, being exactly ninety. At ninety-two it can touch three: a day of
 * autumn, a whole winter, a day of spring. The walk was never relying on that,
 * and the tally settles it either way.
 *
 * **Ties go to the season the range ends in.** The walk runs forward and `>=`
 * lets a later season take the lead on equal footing, so forty-five days of
 * winter followed by forty-five of spring come out spring. A range is read
 * towards its end, and that is the season it is heading into.
 */
export function dominantSeason({ start, end, latitude }) {
  const counts = new Map();
  let best = null;
  for (const iso of eachDay(start, end)) {
    const season = seasonOf(iso, latitude);
    const count = (counts.get(season) ?? 0) + 1;
    counts.set(season, count);
    if (best === null || count >= counts.get(best)) best = season;
  }
  return best;
}
