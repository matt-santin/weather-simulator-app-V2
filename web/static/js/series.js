/**
 * What the two views of a series agree on before either draws anything.
 *
 * There is one thing in it today, and it is here rather than in band.js for the
 * reason CLAUDE.md rule 3 gives about the sky class: the strip and the chart
 * both have to mark the seam, and a rule held in two places diverges — the more
 * quietly, the more obvious it looks. Reading "observed" instead of "not
 * simulated" is exactly the kind of slip that would go unnoticed in one of the
 * two and not the other.
 *
 * The server holds no version of this, so nothing here is a second copy of
 * anything: where the simulated begins is written on every day, in `origin`.
 * What is derived is only *which* crossing deserves a mark.
 */

/**
 * Where the simulated begins, as an index into the series, or `-1`.
 *
 * Only a crossing counts. A range lying wholly in the future has no bank to
 * leave, and a mark on the very first day would announce a passage that never
 * happens — the warning at the top of the page is what covers that case.
 *
 * Anything that is not simulated counts as a bank, forecast days included.
 * A range starting tomorrow runs forecast then simulated, never observed, and
 * its one real seam would go unmarked if this looked for observed days.
 */
export function seamIndex(days) {
  let bankSeen = false;
  for (const [index, day] of days.entries()) {
    if (day.origin === "simulated") {
      if (bankSeen) return index;
    } else {
      bankSeen = true;
    }
  }
  return -1;
}
