/**
 * The bar shared by the results page, the map page and the map of the climates:
 * home on the left, the season the first two show, then a tab for each page
 * (the place, the weather map, the climate map), the current one filled. Each page calls `fillNav` whenever what it shows changes;
 * a tab with no address is hidden (a map opened without a place has no place
 * tab).
 */

import { texts } from "./i18n.js";

const context = document.getElementById("nav-context");
const placeTab = document.getElementById("nav-place");
const mapTab = document.getElementById("nav-map");
const climateTab = document.getElementById("nav-climate");

/** "Été 2063", "Hiver 2080-2081": a winter runs into the next year. */
export function seasonLabel(season, year) {
  const years = season === "winter" ? `${year}-${year + 1}` : String(year);
  return `${texts.season[season] ?? ""} ${years}`.trim();
}

/**
 * `current`: "place", "map" or "climate". `season` and `year` may be null
 * (dates that are not a season): no context then.
 */
export function fillNav({
  current, season = null, year = null, place = null, placeHref = null, mapHref = null, climateHref = null,
}) {
  context.textContent = season && year !== null ? seasonLabel(season, year) : "";
  tab(placeTab, placeHref, current === "place", place, texts.nav.placeTitle(place ?? ""));
  tab(mapTab, mapHref, current === "map", texts.nav.map, texts.nav.mapTitle, texts.nav.mapShort);
  if (climateTab) {
    tab(climateTab, climateHref, current === "climate", texts.nav.climate, texts.nav.climateTitle, texts.nav.climateShort);
  }
}

/** A tab; `short` is its word on a phone (the stylesheet shows one or the other). */
function tab(link, href, here, label, title, short = null) {
  link.hidden = !href;
  if (!href) return;
  link.href = href;
  if (short) {
    const long = document.createElement("span");
    long.className = "site-nav-long";
    long.textContent = label;
    const brief = document.createElement("span");
    brief.className = "site-nav-short";
    brief.textContent = short;
    brief.setAttribute("aria-hidden", "true");
    link.replaceChildren(long, brief);
  } else {
    link.textContent = label;
  }
  link.title = title;
  if (here) link.setAttribute("aria-current", "page");
  else link.removeAttribute("aria-current");
}
