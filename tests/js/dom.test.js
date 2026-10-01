/**
 * The two node builders, and the one difference between them.
 *
 * Worth an executable check for a reason the stub cannot show on its own: an
 * SVG tag built in the HTML namespace parses, appends and inherits the
 * stylesheet, and draws nothing whatsoever. There is no error, no warning and
 * no mark — the page simply comes out empty where a chart was. What is pinned
 * here is that `svg` reaches for the other namespace and that a class lands on
 * the attribute, which is the form both kinds of element answer to.
 */

import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { install } from "./dom-stub.js";

install();

const { el, svg } = await import("../../web/static/js/dom.js");

const SVG_NAMESPACE = "http://www.w3.org/2000/svg";

describe("building a node", () => {
  it("puts the class where both namespaces read it", () => {
    assert.equal(el("p", { className: "card-day" }).attrs.class, "card-day");
    assert.equal(svg("path", { className: "curve high" }).attrs.class, "curve high");
  });

  it("leaves an attribute off rather than setting it empty", () => {
    const node = el("span", { attrs: { "aria-label": undefined, title: "era5" } });

    assert.equal("aria-label" in node.attrs, false);
    assert.equal(node.attrs.title, "era5");
  });

  it("writes text as text, and takes children", () => {
    const node = el("p", { text: "0,4" }, [el("span", { text: "mm" })]);

    assert.equal(node.textContent, "0,4");
    assert.equal(node.children.length, 1);
    assert.equal(node.children[0].textContent, "mm");
  });
});

describe("a mark of a chart", () => {
  it("is built in the SVG namespace, where an HTML element would draw nothing", () => {
    assert.equal(svg("svg").namespace, SVG_NAMESPACE);
    assert.equal(svg("rect").namespace, SVG_NAMESPACE);
  });

  it("is not what el builds", () => {
    assert.equal(el("div").namespace, null);
  });
});
