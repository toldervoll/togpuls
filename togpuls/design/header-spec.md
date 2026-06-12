# Header-redesign — spesifikasjon

Mockup: `header-mockup.html` (åpne i nettleser, knapp nederst for mørk modus).
Gjelder `header.hdr` i `static/index.html`, `static/styles.css`, `static/app.js`.

## Problemer i dagens header

1. Tittelen (`#stop-name` + `#stop-arrow`) duplikerer rutevelgeren (`#from-select` → `#to-select`).
2. Alt ligger på én rad uten responsiv håndtering, innholdet brekker stygt.
3. Temaknappen har tekstetikett og annen høyde enn Apply-knappen.
4. `#updated` viser full `18:43:52`-presisjon og prefiks-tekst som tar plass.

## Målbilde

### Bred skjerm (≥900px) — én rad

`[ 18:43–20:13  90 min ] | [ fra → til  Vis ] [ live  oppdatert 18:43  ☾ ]`

- Tidsvinduet (`#window`) fungerer som tittel, til venstre. Klokkeslett i
  semibold, varighet i muted ved siden av. Vertikal skillelinje mot rutevelgeren.
- Rutevelgeren fyller midten: selects med `flex: 1; min-width: 0`.
- Høyre gruppe: badges (`#loading-badge`/`#stale-badge`), `#updated`, temaknapp.

### Mellomstor (~600–900px) og mobil — to rader

- Rad 1: fra-select → til-select, Vis-knapp, temaknapp (ikon).
- Rad 2 (metarad): tidsvindu · varighet · oppdatert-tid · badge, i muted/small.
- Metaraden får `padding-left` lik selectens innvendige padding + border
  (13px ved 12px padding + 1px border), slik at teksten flukter med
  teksten inne i selecten over.

## Detaljkrav

- H1: fjernes visuelt. Behold en visually-hidden h1 ("togpuls") for
  tilgjengelighet. Rutevelgeren er eneste stedsangivelse.
- Apply-knappen omdøpes til **«Vis»**.
- Temaknapp: kun ikon (☾/☀), `aria-label` og `title`. Fjern tekstetiketten.
- Lik kontrollhøyde: `.dest-select`, `.apply-btn` og `.theme-toggle` deler
  samme høyde (36px, `box-sizing: border-box`). Bruk en felles CSS-variabel,
  f.eks. `--ctrl-h`.
- `#updated`: vis «oppdatert HH:MM», ikke sekunder.
- Breakpoints: én rad ≥900px, to rader under. Under ~600px samme struktur
  som mellomstor, bare strammere gaps og kortere stasjonsnavn får plass
  via `min-width: 0` på selects.
- Behold alle eksisterende id-er som `static/app.js` bruker, eller oppdater
  app.js tilsvarende. Ingen funksjonsendringer, kun layout/markup/stil.
- Test lys og mørk modus, og 375px-viewport.
