# Type

Three families, self-hosted. The `@font-face` blocks that declare them are at
the top of `src/App.css`; every rule reaches them through the four tokens
below rather than naming a family directly.

    --font-body     Archivo          the interface
    --font-display  Archivo          headings (same family, separate token)
    --font-label    Archivo Narrow   labels in the fixed 250px rails
    --font-data     Azeret Mono      measured values only

The split is argued in `7e7c81b`: Archivo Narrow exists because the rails are
a fixed width and labels were breaking to two lines, and mono is reserved for
coordinates, identifiers and telemetry -- a monospace face on a word label is
decoration pretending to be engineering.

## Why these files are in the repo

They were loaded from `fonts.googleapis.com` until now, which made the whole
typography depend on the venue's network. On a dead or captive connection the
stylesheet fails silently, every family falls back to `system-ui`, and there
is no error to notice -- the interface simply stops looking like itself.
152 KB in the repo buys that away.

`*.mp4` is gitignored; `*.woff2` deliberately is not.

## What was downloaded

Variable fonts, one file per subset rather than one per weight:

    archivo-latin.woff2              35 KB   wght 300-800
    archivo-latin-ext.woff2          32 KB   wght 300-800
    archivo-narrow-latin.woff2       18 KB   wght 400-700
    archivo-narrow-latin-ext.woff2   16 KB   wght 400-700
    azeret-mono-latin.woff2          26 KB   wght 400-500
    azeret-mono-latin-ext.woff2      14 KB   wght 400-500

The weight ranges matter: `font-weight: 800` and `font-weight: 300` appear in
`App.css` but neither cut was among the static weights being fetched before,
so the browser was faking both. A variable file covers the range, and those
rules now get a drawn weight.

`latin-ext` carries the Turkish letters (ğ ş İ) and the `unicode-range` on
each face means it is only fetched when a glyph needs it. The `vietnamese`
subset Google also serves was dropped.

## Refreshing them

Ask the CSS API with a Chrome user agent -- without one it answers with TTF
for old browsers instead of WOFF2 -- then pull the URLs it names:

    curl -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 \
      (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36" \
      "https://fonts.googleapis.com/css2?family=Archivo:wght@300..800\
&family=Archivo+Narrow:wght@400..700&family=Azeret+Mono:wght@400..500&display=swap"

The `wght@a..b` range form is what makes it serve the variable file; listing
weights as `wght@400;500;600` gets static cuts instead. Copy the
`unicode-range` values across with the files -- they are what keeps latin-ext
off the wire on an English screen.

## Licence

All three are SIL Open Font License 1.1, which permits redistribution inside
a project like this one. Sources:

    Archivo, Archivo Narrow   Omnibus-Type
    Azeret Mono               Displaay Type Foundry, Martin Vacha

Upstream licence text lives at `ofl/<family>/OFL.txt` in `google/fonts`.
