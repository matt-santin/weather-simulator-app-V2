/**
 * The three things both pages need to put text on screen.
 *
 * `applyTexts` is what lets the HTML stay static while every sentence still
 * lives in i18n.js: a page marks a slot with `data-text="form.place"` and this
 * fills it. No sentence in a page file, no page file in the dictionary.
 *
 * `el` builds a node with `textContent`, never `innerHTML`. The place name
 * travels in the query string, so it is visitor input arriving as text — the
 * one habit that keeps it from being anything else.
 *
 * `svg` is the same builder in the other namespace, and it exists because a
 * chart cannot be drawn without it: `createElement("path")` in an HTML document
 * makes an unknown HTML element that lays out as nothing and draws nothing at
 * all. The two share everything below the first line.
 */

import { texts } from "./i18n.js";

/** "form.place" → the string at texts.form.place, or undefined. */
export function lookup(path) {
  return path.split(".").reduce((node, key) => node?.[key], texts);
}

/**
 * Fill every slot marked in the markup.
 *
 * `data-text="a.b"` sets the element's text; `data-attr-placeholder="a.b"` sets
 * its placeholder, and so on for any attribute.
 */
export function applyTexts(root = document) {
  for (const node of root.querySelectorAll("[data-text]")) {
    node.textContent = lookup(node.dataset.text) ?? "";
  }
  for (const node of root.querySelectorAll("*")) {
    for (const [key, path] of Object.entries(node.dataset)) {
      if (key.startsWith("attr")) {
        // dataset gives back "attrAriaLabel"; the attribute is "aria-label".
        const name = key
          .slice(4)
          .replace(/[A-Z]/g, (letter) => `-${letter.toLowerCase()}`)
          .replace(/^-/, "");
        node.setAttribute(name, lookup(path) ?? "");
      }
    }
  }
}

const SVG_NAMESPACE = "http://www.w3.org/2000/svg";

/** A node, its classes, its text, its children. */
export function el(tag, options = {}, children = []) {
  return fill(document.createElement(tag), options, children);
}

/**
 * The same, for the marks of a chart: a `path`, a `rect`, a `g`.
 *
 * The namespace is the whole difference. An SVG tag built through
 * `createElement` is an HTML element wearing an SVG name — it parses, it appends,
 * it inherits the stylesheet, and it draws nothing. The failure is silent and
 * looks like a geometry bug, which is why the two builders are named apart
 * rather than left to a flag on one.
 */
export function svg(tag, options = {}, children = []) {
  return fill(document.createElementNS(SVG_NAMESPACE, tag), options, children);
}

function fill(node, { className, text, attrs } = {}, children = []) {
  // The attribute rather than the property, because `className` on an SVG
  // element is a read-only `SVGAnimatedString`: assigning to it does nothing,
  // and does it without a word. On an HTML element the two are the same thing.
  if (className) node.setAttribute("class", className);
  if (text !== undefined) node.textContent = text;
  for (const [name, value] of Object.entries(attrs ?? {})) {
    // An attribute with nothing to say is left off rather than set empty: an
    // `aria-label=""` is not the absence of a label, it is an empty one.
    if (value !== undefined && value !== null && value !== "") node.setAttribute(name, value);
  }
  node.append(...children);
  return node;
}
