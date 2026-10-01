/**
 * Transport, and nothing else.
 *
 * The browser fetches the data because Open-Meteo limits per IP address: a
 * server doing it would funnel every visitor through one address and reach the
 * ceiling immediately. So the calls happen here — and what to call is decided
 * there.
 *
 * **Nothing in this file reads a value.** No date is cut, no model is chosen, no
 * threshold is compared, no average is taken. The server hands over finished
 * URLs; this calls fetch on each and posts the answers back untouched. Not
 * because a browser may derive nothing — CLAUDE.md rule 3 asks something
 * narrower, that a rule the server already holds not be kept a second time here
 * — but because a transport module that reads its cargo stops being one. The
 * earlier prototype held the sky-class logic twice, once here and once in
 * Python, and the two drifted, on five lines of threshold comparisons.
 *
 * The one thing worth knowing about the exchange: /api/plan and /api/days are
 * two halves of the same search, and `today` travels from the first to the
 * second so that both agree on where the observed stops and the simulated
 * starts. It is echoed back verbatim, never recomputed here — a browser clock
 * is the visitor's, and the seam is not.
 *
 * It does not write, either: the sentences it hands to the visitor come from
 * i18n.js, where docs/application.md asks that every visible string live.
 */

import { texts } from "./i18n.js";

/** A refusal from the API, carrying the sentence meant for the visitor. */
export class SearchError extends Error {
  constructor(message, status, options) {
    super(message, options);
    this.name = "SearchError";
    this.status = status;
  }
}

/**
 * How long the browser waits before giving up, in milliseconds.
 *
 * **A request without one of these does not fail, it hangs**, and a page that
 * hangs says nothing at all: the results page sits on "Récupération des
 * données…" with no error and no end. That is not hypothetical — Open-Meteo's
 * climate endpoint was observed stalling twice in a row, 25 then 45 seconds
 * without a byte, before answering the same query in 0,17.
 *
 * **Two values, because the two ends fail differently.** Our own API does no
 * network of its own on the request path — it plans, or it reads payloads back
 * — so fifteen seconds there means something is broken rather than slow.
 * Open-Meteo is a public service across the internet, and its normal answer to
 * the widest search this application allows is well under two seconds; thirty
 * is fifteen times that, which is long enough that only a genuine stall reaches
 * it.
 *
 * **Short would be worse than long here.** An aborted request has still cost
 * the visitor their Open-Meteo quota, which is counted against their own
 * address; cutting off a slow but living answer spends it for nothing, and the
 * retry spends it again. Hence a ceiling rather than a deadline. The offline
 * client is more patient still — `client.py` waits 180 seconds — and it is
 * right to be: nobody is watching a script.
 *
 * Neither number is served by /api/config, and neither should be: the server
 * holds no version of how long a browser is willing to wait, so there is no
 * second copy for rule 3 to be about.
 */
const API_TIMEOUT_MS = 15_000;
const UPSTREAM_TIMEOUT_MS = 30_000;

/**
 * The sentence a failed call earns, told apart from the one it was given.
 *
 * A timeout is not the failure the caller had in mind. `upstreamFailed` names
 * the rate limit, which is the common cause and the one the visitor can act on
 * by waiting; a stall is neither, and offering to wait would be advice for a
 * problem they do not have. So the wait that never ends gets its own sentence,
 * for the same reason i18n.js gives for keeping the other two apart.
 */
function reasonFor(cause, message) {
  return cause?.name === "TimeoutError" ? texts.transport.tookTooLong : message;
}

async function getJson(url, message, { timeout = UPSTREAM_TIMEOUT_MS } = {}) {
  let response;
  try {
    response = await fetch(url, { signal: AbortSignal.timeout(timeout) });
  } catch (cause) {
    // A dropped connection, a DNS failure, a blocked request, a stall that ran
    // out its clock: no status at all in any of those cases.
    throw new SearchError(reasonFor(cause, message), 0, { cause });
  }
  if (!response.ok) {
    throw new SearchError(message, response.status);
  }
  // The body is under the same clock as the headers, a stalled stream being as
  // silent as a stalled request — and it is read inside the guard for that.
  try {
    return await response.json();
  } catch (cause) {
    throw new SearchError(reasonFor(cause, message), 0, { cause });
  }
}

// Two sentences, because the two failures are not the visitor's to confuse.
// Why they read the way they do is explained where they are written, in i18n.js.
const { upstreamFailed: UPSTREAM_FAILED, serviceFailed: SERVICE_FAILED } = texts.transport;

/**
 * The constants the API enforces, so the form can refuse the same things it
 * does rather than keeping its own copy of the rules.
 */
export function loadConfig() {
  // Our own API, so the shorter of the two clocks: this one crosses no internet.
  return getJson("/api/config", SERVICE_FAILED, { timeout: API_TIMEOUT_MS });
}

/**
 * Turn a place name into candidate locations.
 *
 * The geocoding address comes from the config rather than being written here,
 * so this file holds no knowledge of Open-Meteo at all. Nominatim is not used:
 * its terms forbid intensive use.
 */
export async function geocode(name, config, { count = 5, language = "fr" } = {}) {
  const url = new URL(config.geocoding_url);
  url.searchParams.set("name", name);
  url.searchParams.set("count", String(count));
  url.searchParams.set("language", language);
  url.searchParams.set("format", "json");

  const payload = await getJson(url.toString(), UPSTREAM_FAILED);
  // Absent rather than empty when nothing matches. Not a decision about the
  // data — an empty list and a missing key mean the same thing here.
  return payload.results ?? [];
}

/**
 * One search: the server reads the store and returns the classified days.
 * Every value in the answer was computed there.
 */
export async function search({ latitude, longitude, start, end }) {
  const query = new URLSearchParams({ latitude, longitude, start, end });
  let response;
  try {
    response = await fetch(`/api/days?${query}`, { signal: AbortSignal.timeout(API_TIMEOUT_MS) });
  } catch (cause) {
    throw new SearchError(reasonFor(cause, texts.transport.serviceFailed), 0, { cause });
  }
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    throw new SearchError(payload?.message ?? texts.transport.searchFailed, response.status);
  }
  return payload;
}
