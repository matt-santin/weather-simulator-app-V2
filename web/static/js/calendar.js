/**
 * ISO days, and the one way this project does arithmetic on them.
 *
 * No DOM, no state, no fetching — the neighbour of `present.js`, and
 * `node --test` is enough to check it.
 *
 * **Everything here reads a date at noon UTC**, and that single decision is the
 * reason the file exists. Midnight in a local zone is 23 or 25 hours from the
 * next one twice a year, so a span comes out a day short and a walk skips or
 * repeats a day — twice a year, in one hemisphere, which is exactly the kind of
 * failure nobody reproduces. Noon is far enough from both edges that no offset
 * on Earth can cross a date boundary.
 *
 * **It was written in three places before it was written here.** `bounds.js`
 * measured a span, `compare.js` shifted a range, `season.js` walked one — each
 * with its own `24 * 60 * 60 * 1000`, its own `T12:00:00Z`, and a comment
 * pointing at the other two. That is the double exemplaire CLAUDE.md rule 3 is
 * about, and the rule does not care that the three lines are obvious: nobody
 * re-reads an obvious line, which is what lets it drift.
 *
 * Dates are ISO strings throughout — "2046-07-14" — and they compare correctly
 * as strings, so ordering never needs to come through here at all.
 */

/** One day, in milliseconds. Exact, these being UTC stamps and not local ones. */
export const DAY = 24 * 60 * 60 * 1000;

/** An ISO day as a stamp, read at noon UTC. */
export const at = (date) => Date.parse(`${date}T12:00:00Z`);

/** A stamp back to an ISO day. */
export const iso = (stamp) => new Date(stamp).toISOString().slice(0, 10);

/** Two digits, so a month and a day sit in an ISO date the way they must. */
export const pad = (n) => String(n).padStart(2, "0");

/** How many days a range shows, both ends counted. */
export function span(start, end) {
  return Math.round((at(end) - at(start)) / DAY) + 1;
}

/**
 * Every day of the range, both ends counted.
 *
 * An unusable range — either end missing, or running backwards — yields nothing
 * rather than throwing; the form and the API both refuse one long before any
 * caller here sees it.
 */
export function* eachDay(start, end) {
  if (!start || !end || start > end) return;
  const last = at(end);
  for (let stamp = at(start); stamp <= last; stamp += DAY) yield iso(stamp);
}
