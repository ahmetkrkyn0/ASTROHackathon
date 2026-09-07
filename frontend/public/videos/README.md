# Background video

`moon-backdrop-1080.mp4` is the clip the mission deck plays. It is named in
`CLIP_SRC` at the top of `src/SpaceBackdrop.tsx`.

    frontend/public/videos/moon-backdrop-1080.mp4    3.8 MB, served
    media-src/Moon_Phases_Near_Far_Waning_4K.mp4     270 MB, source only

`*.mp4` is gitignored, so neither file is in the repo and a fresh clone falls
back to the `starimg.jpeg` poster with no code change and no error state. Pass
them around out of band -- the source is well past GitHub's 100 MB limit.

The source lives in `media-src/` rather than here on purpose: Vite copies
everything under `public/` into `dist/` verbatim, so a 270 MB file sitting in
this directory would ride along into every production build.

## Re-encoding

The source is 3840x2160 at 60 fps and 151 Mbps -- an intermediate-grade
master, not a web asset. It was reduced 71x with no visible loss at the size
and opacity this plays at:

    ffmpeg -i media-src/Moon_Phases_Near_Far_Waning_4K.mp4 \
      -vf "scale=1920:-2,fps=30" \
      -c:v libx264 -profile:v high -crf 26 -preset slow \
      -movflags +faststart -an \
      frontend/public/videos/moon-backdrop-1080.mp4

What each part is for:

- `scale=1920:-2` — 1080p. `-2` keeps the aspect ratio and forces an even
  height, which H.264 requires.
- `fps=30` — halves the frame count. 60 fps buys nothing behind a vignette.
- `-crf 26` — visually fine at this scale; lower the number for more quality
  and more bytes.
- `-movflags +faststart` — moves the index to the front so playback can start
  before the whole file has arrived.
- `-an` — drops audio. The element is muted anyway, and browsers refuse to
  autoplay unmuted video.

## Constraints worth knowing

- H.264 in MP4 is the only combination every browser autoplays.
- Muted is mandatory; the element sets `muted` and `playsInline` so iOS Safari
  plays inline instead of going fullscreen.
- Make the loop seamless — first and last frame should match, or the cut shows
  on every cycle.
- `prefers-reduced-motion: reduce` viewers never see it play. They get the
  poster image instead, handled in `SpaceBackdrop`.

## How it is used

One element, mounted once, never remounted — so the clip runs unbroken across
all three phases. `SpaceBackdrop` takes a `stage` and a `frozen` flag:

- **landing** → `ambient`, opacity 0.4, zoomed 2.1x. The zoom matters: at 1x
  the clip's own disc sits beside the landing page's interactive moon and
  reads as a second moon. Pushed in, it is lunar surface and starfield.
- **cinematic** → `feature`, opacity 1.0. The clip is the screen, so the
  vignette that exists to protect UI legibility drops to 0.45.
- **app** → `deck`, opacity 0.55, behind the console.

`frozen` latches the first time a route point is armed and never unlatches:
once you are placing points on the map, motion behind a precision click
target is a distraction rather than atmosphere.
