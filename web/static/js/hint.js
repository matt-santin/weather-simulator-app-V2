/**
 * A small "?" that shows a note: on hover, on keyboard focus, and on a tap,
 * since a touch screen has no hover.
 *
 * The markup: a `<button data-hint aria-controls="ID" aria-expanded="false">`
 * and, anywhere on the page, the note `<p id="ID" role="tooltip" hidden>`. A
 * click pins the note open until a second click, Escape, or a click elsewhere.
 */

export function wireHints(root = document) {
  for (const button of root.querySelectorAll("button[data-hint][aria-controls]")) {
    const note = document.getElementById(button.getAttribute("aria-controls"));
    if (!note) continue;
    let pinned = false;
    const set = (open) => {
      note.hidden = !open;
      button.setAttribute("aria-expanded", String(open));
    };
    const close = () => {
      pinned = false;
      set(false);
    };
    button.addEventListener("mouseenter", () => set(true));
    button.addEventListener("mouseleave", () => pinned || set(false));
    button.addEventListener("focus", () => set(true));
    button.addEventListener("blur", close);
    button.addEventListener("click", () => {
      pinned = !pinned;
      set(pinned);
    });
    button.addEventListener("keydown", (event) => event.key === "Escape" && close());
    // A tap elsewhere: Safari does not focus a tapped button, so no blur comes.
    document.addEventListener("click", (event) => {
      if (event.target !== button && !note.contains(event.target)) close();
    });
  }
}
