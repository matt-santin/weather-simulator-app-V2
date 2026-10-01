/**
 * The same dates, another year: the arithmetic behind the comparison curves.
 *
 * A simulated 39 °C says nothing to a reader who does not know what a 14 July
 * used to be — the lesson is in the gap, not in the value. So the chart can carry
 * a second year, drawn under the first. What has to be settled before anything is
 * drawn is which dates that second year covers and how its days line up with the
 * ones on screen. That is all this file does.
 *
 * No DOM, no state, no fetching — the neighbour of `season.js` and `bounds.js`,
 * and `node --test` is enough to check it.
 *
 * **Nothing here is a second copy of a server rule.** The comparison is an
 * ordinary search of this site: the shifted range goes back through `/api/plan`
 * and `/api/days`, which cut it into segments, choose the models and classify the
 * sky exactly as they do for the range on screen. That is what makes the two
 * curves comparable at all — CLAUDE.md rule 2 asks that every displayed quantity
 * be computed identically over the whole series, and the cheapest way to obey it
 * was to compute nothing new.
 *
 * **A past range is cheap and unconditional.** Two requests, ERA5-Land and ERA5;
 * no correction grid required, since the API only refuses an uncovered place when
 * the range reaches past today. A comparison therefore works everywhere in the
 * world, including where the future is refused.
 */

import { DAY, at, iso, span } from "./calendar.js";

/**
 * The year the menu opens on, and it was measured rather than picked.
 *
 * `scripts/model_selection/reference_year.py` scores each year as its distance
 * from the mean of its period, in standard deviations, averaged over five French
 * sites. **An intuitive year is wrong by about the size of the signal**: 1980
 * sits at −2,00 σ in summer — the coldest of its thirty at four of the five —
 * and comparing a simulated summer to it would show roughly twice the warming
 * there is. 2003, at +3,25 σ, would show a cooling.
 *
 * The most ordinary year of the earliest usable period is **1991** (+0,49 σ in
 * summer, −0,46 in winter, +0,03 over the year, on 1979-1994). Earliest matters
 * on its own: the French sites warm by 0,92 °C between 1979-1988 and 1999-2008,
 * so a reference taken in the 2000s spends a degree of the signal before it
 * starts.
 *
 * The visitor may pick any other year — this is a default, not a gate. What the
 * default buys is that nobody lands on 1980 without meaning to.
 */
export const ORDINARY_YEAR = 1991;

/**
 * One date moved to another year, the 29th of February included.
 *
 * **JavaScript does not refuse an impossible date, it slides it.** `2025-02-29`
 * parses, and comes back as 1 March — a day that is not the one asked for, in
 * silence, on the one date of the calendar where it matters. So the shift is
 * checked by reading it back: a date that does not survive the round trip is not
 * a date, and the eve stands in for it. Nothing but 29 February can fail here,
 * every other month-day existing in every year.
 */
function shiftDate(date, year) {
  const wanted = `${year}-${date.slice(5)}`;
  return iso(at(wanted)) === wanted ? wanted : `${year}-02-28`;
}

/**
 * The same stretch of calendar in another year, as `{ start, end }`.
 *
 * **The range may span two calendar years** — a winter opens in December and
 * closes in March — so the distance between the two years is carried over rather
 * than both ends being put in the same one.
 *
 * **And the shift can gain a day.** From 1 February to 3 May is 92 days in a
 * common year and 93 in a leap one, which would be one more than the API allows.
 * The shifted range is therefore trimmed from its end, and the grey curve simply
 * stops a day early — a shape `runs()` already draws, being the same thing as a
 * series that ran out. Trimming the end rather than the start keeps the two
 * curves aligned where the eye starts reading.
 *
 * `maxDays` comes from `/api/config`, never written here: a 92 in this file would
 * go on saying 92 the day the API said 120.
 */
export function shiftRange({ start, end }, year, maxDays) {
  const offset = Number(end.slice(0, 4)) - Number(start.slice(0, 4));
  const shifted = { start: shiftDate(start, year), end: shiftDate(end, year + offset) };

  const excess = span(shifted.start, shifted.end) - maxDays;
  if (excess > 0) shifted.end = iso(at(shifted.end) - excess * DAY);
  return shifted;
}

/**
 * The compared days, laid alongside the days on screen, one slot each.
 *
 * Returns an array as long as `days`, each slot carrying the compared day of the
 * **same month and day** or `null`. Never an alignment by index: the API serves
 * the first day it actually has, not the one that was asked for, and a 29
 * February with no counterpart has to stay a hole rather than shove every day
 * after it out by one.
 *
 * **A day that is not `observed` is dropped**, and that is a guard rather than a
 * decision. The menu only offers years whose range has fully passed, so this
 * should never fire; if it did, the alternative would be a forecast day drawn in
 * grey and read as the old climate. `origin` is served on every day — this reads
 * a field, it does not recompute one.
 */
export function alignByCalendar(days, compared) {
  const found = new Map();
  for (const day of compared) {
    if (day.origin === "observed") found.set(day.date.slice(5), day);
  }
  return days.map((day) => found.get(day.date.slice(5)) ?? null);
}

/**
 * The years the menu may offer, earliest first: those whose shifted range lies
 * wholly inside an observed period (ERA5). A comparison with a simulated year
 * would not be another year of weather, it would be the same trajectory
 * wearing grey. The periods are served by `/api/config`.
 */
export function selectableYears(range, config) {
  const years = [];
  for (const period of config.periods.filter((p) => p.origin === "observed")) {
    const first = Number(period.start.slice(0, 4));
    const last = Number(period.end.slice(0, 4));
    for (let year = first; year <= last; year += 1) {
      const shifted = shiftRange(range, year, config.max_days);
      if (shifted.start >= period.start && shifted.end <= period.end) years.push(year);
    }
  }
  return years;
}
