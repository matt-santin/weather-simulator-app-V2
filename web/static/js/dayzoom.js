/**
 * The calendar's two behaviours: moving between days, and the enlarged card.
 *
 * On the calendar a card shows its date, its pictogram and its maximum, nothing
 * else. The rest of the day (minimum, sky, rain, wind) is still in the card for the
 * screen reader, and comes on screen in an enlarged copy of the card, drawn
 * over it while the pointer rests on it or while it has the focus.
 *
 * **A copy laid over the page, not the card itself grown.** The calendar is a
 * scrolled box, and a card scaled inside it would be cut at the box's edges:
 * the top week upward, the side columns outward. The copy is fixed to the
 * window and placed over the card, kept inside the window. It is hidden from
 * screen readers, which already have the card it copies.
 *
 * **One card in the tab order, the arrows for the rest.** Ninety-two tab stops
 * would stand between the visitor and the chart. Left and right step a day, up
 * and down to the card in the same column on the row above or below (a day on
 * the list a narrow window shows: one column), and focusing a
 * card scrolls it into view. A tap focuses a card too, which is what opens the
 * copy on a touch screen, where there is no hover; a tap elsewhere closes it.
 *
 * On the list a narrow window shows, every card already carries everything,
 * and no copy is drawn.
 */

const GROWTH = 1.7;
const MIN_WIDTH = 240;
const MARGIN = 8;

/** Wire the calendar `grid` (the ol of cards) and the box that scrolls it. */
export function attachZoom(grid, scroller) {
  const cards = () => [...grid.querySelectorAll(".card")];
  const isCalendar = () => getComputedStyle(grid).gridTemplateColumns.split(" ").length >= 7;
  let zoom = null;
  let shown = null;

  const first = cards()[0];
  if (first) first.tabIndex = 0;
  for (const card of cards().slice(1)) card.tabIndex = -1;

  function close() {
    zoom?.remove();
    zoom = null;
    shown = null;
  }

  function open(card) {
    close();
    if (!isCalendar()) return;
    const tile = card.getBoundingClientRect();
    const copy = card.cloneNode(true);
    copy.classList.add("card--zoom");
    copy.removeAttribute("tabindex");
    copy.removeAttribute("title");
    copy.setAttribute("aria-hidden", "true");
    const width = Math.max(tile.width * GROWTH, MIN_WIDTH);
    copy.style.width = `${width}px`;
    document.body.append(copy);
    zoom = copy;
    shown = card;
    place();
    // From the card's own size to its enlarged one, centred on the card.
    copy.style.setProperty("--from", String(tile.width / width));
    requestAnimationFrame(() => copy.classList.add("is-open"));
  }

  /** Over the card, centred on it, kept inside the window. */
  function place() {
    const tile = shown.getBoundingClientRect();
    const left = tile.left + tile.width / 2 - zoom.offsetWidth / 2;
    const top = tile.top + tile.height / 2 - zoom.offsetHeight / 2;
    zoom.style.left = `${Math.round(clamp(left, window.innerWidth - zoom.offsetWidth))}px`;
    zoom.style.top = `${Math.round(clamp(top, window.innerHeight - zoom.offsetHeight))}px`;
  }

  // A scroll moves the card from under the copy. The copy of the focused card
  // follows it, since focusing a card is what scrolls it into view; the copy
  // of a card under the pointer closes, the pointer no longer being on it.
  function follow() {
    if (!zoom) return;
    if (shown === document.activeElement) place();
    else close();
  }

  function move(card, next) {
    if (!next) return;
    card.tabIndex = -1;
    next.tabIndex = 0;
    next.focus();
  }

  // The mouse alone: a touch fires `pointerout` as soon as the finger lifts,
  // and is served by the focus below.
  grid.addEventListener("pointerover", (event) => {
    const card = event.target.closest(".card");
    if (event.pointerType === "mouse" && card && !card.contains(event.relatedTarget)) open(card);
  });
  grid.addEventListener("pointerout", (event) => {
    const card = event.target.closest(".card");
    if (event.pointerType === "mouse" && card && !card.contains(event.relatedTarget)) close();
  });

  grid.addEventListener("focusin", (event) => {
    const card = event.target.closest(".card");
    if (!card) return;
    for (const other of cards()) other.tabIndex = other === card ? 0 : -1;
    open(card);
  });
  grid.addEventListener("focusout", close);

  grid.addEventListener("keydown", (event) => {
    const card = event.target.closest(".card");
    if (!card) return;
    const all = cards();
    const at = all.indexOf(card);
    const targets = {
      ArrowLeft: () => all[at - 1],
      ArrowRight: () => all[at + 1],
      ArrowUp: () => below(all.slice(0, at).reverse(), card),
      ArrowDown: () => below(all.slice(at + 1), card),
    };
    if (event.key in targets) {
      event.preventDefault();
      move(card, targets[event.key]());
    } else if (event.key === "Escape") {
      close();
    }
  });

  scroller.addEventListener("scroll", follow, { passive: true });
  window.addEventListener("scroll", follow, { passive: true });
  window.addEventListener("resize", close);
}

/**
 * The first card of `candidates` in the same column as `card`, on another row.
 * A week cut by the turn of a month has no fixed stride, so the column is read
 * from the layout; on the list there is one column, and this is the next card.
 */
function below(candidates, card) {
  return candidates.find(
    (other) => Math.abs(other.offsetLeft - card.offsetLeft) < 2 && other.offsetTop !== card.offsetTop,
  );
}

/** A position kept inside the window, a margin from either edge. */
function clamp(position, last) {
  return Math.max(MARGIN, Math.min(position, last - MARGIN));
}
