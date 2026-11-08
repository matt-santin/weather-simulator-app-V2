/**
 * The bar shared by the results page and the map page: home on the left, the
 * season both pages show, then a tab for each page (the place, Europe), the
 * current one filled. Each page calls `fillNav` whenever what it shows changes;
 * a tab with no address is hidden (a map opened without a place has no place
 * tab).
 */

import { texts } from "./i18n.js";

const context = document.getElementById("nav-context");
const placeTab = document.getElementById("nav-place");
const mapTab = document.getElementById("nav-map");

/** "Été 2063", "Hiver 2080-2081": a winter runs into the next year. */
export function seasonLabel(season, year) {
  const years = season === "winter" ? `${year}-${year + 1}` : String(year);
  return `${texts.season[season] ?? ""} ${years}`.trim();
}

/**
 * `current`: "place" or "map". `season` and `year` may be null (dates that are
 * not a season): no context then.
 */
export function fillNav({ current, season = null, year = null, place = null, placeHref = null, mapHref = null }) {
  context.textContent = season && year !== null ? seasonLabel(season, year) : "";
  tab(placeTab, placeHref, current === "place", place, texts.nav.placeTitle(place ?? ""));
  tab(mapTab, mapHref, current === "map", texts.nav.map, texts.nav.mapTitle);
}

function tab(link, href, here, label, title) {
  link.hidden = !href;
  if (!href) return;
  link.href = href;
  link.textContent = label;
  link.title = title;
  if (here) link.setAttribute("aria-current", "page");
  else link.removeAttribute("aria-current");
}
