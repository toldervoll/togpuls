# Header redesign — specification

Mockup: `header-mockup.html` (open in a browser; button at the bottom
toggles dark mode).
Applies to `header.hdr` in `static/index.html`, `static/styles.css`,
`static/app.js`.

Note: UI strings are Norwegian ("Vis", "oppdatert HH:MM") — keep them as
written here.

## Problems in the previous header

1. The title (`#stop-name` + `#stop-arrow`) duplicated the route picker
   (`#from-select` → `#to-select`).
2. Everything sat on one row with no responsive handling; content wrapped
   badly.
3. The theme button had a text label and a different height from the Apply
   button.
4. `#updated` showed full `18:43:52` precision plus prefix text.

## Target design

### Wide screens (≥900px) — single row

`[ 18:43–20:13  90 min ] | [ from → to  Vis ] [ live  oppdatert 18:43  ☾ ]`

- The time window (`#window`) acts as the title, on the left. Time in
  semibold, duration muted next to it. Vertical divider towards the route
  picker.
- The route picker fills the middle: selects with `flex: 1; min-width: 0`.
- Right-hand group: badges (`#loading-badge`/`#stale-badge`), `#updated`,
  theme button.

### Medium (~600–900px) and mobile — two rows

- Row 1: from-select → to-select, Vis button, theme button (icon only).
- Row 2 (meta row): time window · duration · updated time · badge, in
  muted/small style.
- The meta row gets `padding-left` equal to the select's inner padding +
  border (13px at 12px padding + 1px border), so the text aligns with the
  text inside the select above.

## Detailed requirements

- H1: hidden visually. Keep a visually-hidden h1 ("togpuls") for
  accessibility. The route picker is the only place indicator.
- The Apply button is renamed to **"Vis"**.
- Theme button: icon only (☾/☀), with `aria-label` and `title`. No text
  label.
- Equal control height: `.dest-select`, `.apply-btn` and `.theme-toggle`
  share the same height (36px, `box-sizing: border-box`). Use a shared CSS
  variable, e.g. `--ctrl-h`.
- `#updated`: show "oppdatert HH:MM", no seconds.
- Breakpoints: one row ≥900px, two rows below. Below ~600px the same
  structure as medium, just tighter gaps; long station names fit via
  `min-width: 0` on the selects.
- Keep all existing ids that `static/app.js` uses, or update app.js
  accordingly. No functional changes, only layout/markup/style.
- Test light and dark mode, and a 375px viewport.
