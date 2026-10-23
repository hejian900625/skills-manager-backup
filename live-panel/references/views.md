# live-panel views — extension contract (视图扩展说明)

This is the contract every view author must follow. Read it fully before writing code.

## 0. What a "view" is

The original engine draws absolutely positioned boxes/wires from a JSON config (see SKILL.md,
references/config-schema.md, references/motion-grammar.md, assets/template.html).
A **view** is a new element `{"type":"view","kind":"<kind>", ...}` that lays out a whole diagram
*automatically* inside a rectangle, from data, and animates it as a pure function of time.
Because views compute their own layout from the rect, **the same config must render correctly at
canvas presets 4:5 (1200x1500), 3:4 (1080x1440) and 1:1 (1080x1080) and in both themes
(terminal-dark, light-pastel)** with nothing but `canvas.preset` / `theme.preset` changed.

Six kinds: `nebula` (force-directed relation graph), `timeline` (swimlanes), `funnel`
(pipeline/conversion), `tree` (hierarchy / org chart), `ring` (loop/cycle), `kpi` (dashboard matrix).

## 1. Files (one view = one file, so parallel work never conflicts)

- `assets/views/<kind>.js` — the whole implementation of one view. Plain ES5/ES2017 JS, no imports,
  no network, no external libs. Self-registers: `LP.registerView('<kind>', {...})`.
- `examples/<kind>/config.json` — an AI-agent themed example using this view (written for
  `canvas.preset:"4:5"`, `theme.preset:"light-pastel"` by default; it must ALSO pass when the
  preset/theme are swapped).
- Config keys: list every kind-specific key with its default in section 6 below (the per-view brief).
- Do NOT edit `assets/template.html`, `scripts/*`, `SKILL.md`, `README.md` or other views. If you
  believe the core needs a change, describe it in your PR under "Core requests" instead.

`scripts/livepanel.py build_page` inlines every `assets/views/*.js` (sorted by name) into the page
at `<!--LIVE_VIEWS-->`, so the page stays self-contained.

## 2. Core API (provided by template.html as `window.LP`)

```
LP.registerView(kind, impl)     // impl = {build(ctx), seek(t), events?(lo,hi), check?()}
ctx = {
  e,            // the element config object (your data)
  rect:{x,y,w,h},   // where to draw, canvas px (defaults: full canvas minus titlebar & credit band)
  root,         // a <div> absolutely positioned at rect, size w x h, overflow visible. Draw ONLY inside it.
  svg(tag,attrs)// helper: create an SVG element in the SVG namespace with attributes
  el(tag,cls,style)  // helper: create an HTML element
  CW, CH,       // canvas size
  TH,           // merged theme object (TH.preset is 'terminal-dark' or 'light-pastel', TH.font, TH.titleFont, TH.fontSize, TH.lineHeight, TH.radius ...)
  dark,         // true for terminal-dark
  cc(name),     // 'var(--c-name)' for a theme colour name
  col(name),    // resolved '#rrggbb' of a theme colour name (for canvas/SVG math, colour mixing)
  acc(i),       // colour NAME of accent i (0..5, wraps): 'acc1'..'acc6'
  accf(i),      // colour NAME of the matching soft fill: 'accf1'..'accf6'
  hash(seed,k), // deterministic pseudo random in [0,1)
  mod(a,n), fill(str) /* {var} templating from machine vars */, V /* machine variables */,
  measure(text, px, font) // -> width in px using a canvas 2D context (works for CJK and Latin)
  fit(text, px, maxW, font, minPx) // -> {text, size}: shrinks font down to minPx, then ellipsizes with '…'
  mark(node, kind)    // tag a DOM/SVG node for the checkers: kind = 'text' | 'box' | 'frame' | 'edge'
                      // 'edge' = a connector path/line (verifier checks it does not pass through a 'box')
}
The core sets `root.dataset.view = kind` and `root.dataset.rect = "x,y,w,h"` so checkers can find
every view and its rect. Marked nodes get attribute `data-t` (same mechanism as the original
`window.__check`, which therefore also checks view text for overflow/overlap automatically).
LP.ease = {inOut(x), out(x), smooth(x)}   // easing helpers on [0,1]
```

`impl.build(ctx)` runs once at boot (after fonts are ready). Compute the whole layout here.
`impl.seek(t)` runs every frame; update only attributes/styles/text. NEVER create or remove DOM
nodes in seek (create everything in build, then show/hide). `impl.events(lo,hi)` may return log
events `{t, who, c, m, g}` (same shape machines emit) so a `log` element can narrate the view;
`impl.check()` may return a list of extra problem strings (logic errors, e.g. funnel not monotonic).

## 3. Theme colours available in BOTH presets

Base: `bg bar line line2 dim fg wh dots hl`. New semantic names added by the core:
`acc1..acc6` (strong accents), `accf1..accf6` (soft fills / tints for cards & halos),
`panel` (card background slightly off bg), `grid` (faint grid/rail lines), `ok warn bad` (status),
`muted` (secondary text that still passes 4.5:1 on bg/panel in both themes — the legacy `dim` does not on light-pastel).
Use only these names (via ctx.cc / ctx.col) so both themes work. Never hard-code hex colours.
Dark theme look: monospace, glow, thin lines, near-black bg. Light look: white, pastel fills,
rounded cards, soft shadows, gentle motion.

Fonts: body text uses `TH.font` (CSS var `--font`). Titles/big numbers may use `TH.titleFont`
(CSS var `--font-title`), which is 得意黑 Smiley Sans when `theme.titleFont:"smiley"` is set
(embedded offline by build_page), else equals `--font`.

## 4. Hard rules (the verifier enforces these; failing = rejected)

1. **Determinism**: every visual is a pure function of `t`. No `Math.random`, no `Date`, no
   `performance.now`, no CSS animations/transitions, no requestAnimationFrame inside the view.
   Force layouts (nebula) must be computed in `build` with a fixed seed and a fixed iteration count,
   then animated in `seek` as small deterministic offsets (e.g. sin/cos of t with per-node phase).
2. **Layout never jumps**: the diagram is complete at t=0. Motion = state (packets, highlights,
   counters, progress), never re-layout. Drift amplitudes ≤ 6 px.
3. **Text**: every text node is marked `mark(node,'text')`; it must stay inside its card/box
   (cards marked 'box'; big enclosing panels/lanes marked 'frame'), inside the canvas, and must not
   overlap other text. Use `ctx.fit` so long CJK or English labels shrink/ellipsize instead of
   overflowing. Minimum font size 11 px. Text nodes: `white-space:pre`, explicit `line-height`.
4. **Contrast**: text colour vs its background ≥ 4.5:1 for body, ≥ 3:1 for ≥ 20px titles. Use
   `fg`/`muted` on `bg`/`panel` (not `dim`, see R17); for text on a coloured fill use `fg` (light) or `wh` (dark accent).
5. **Edges never cross through a node/card**: route lines around cards or end them at card borders.
6. **Rhythm**: no element may flash (toggle visibility or colour) faster than every 0.4 s; any
   single highlight lasts ≥ 0.8 s. Three tempos: fast (packets/particles), medium (1–3 s state
   changes), slow (3–6 s focus rotation). Same as motion-grammar.md.
7. **One truth**: numbers shown in two places are the same variable (e.g. funnel stage counts and
   conversion % are computed from one list; the % printed is exactly next/prev).
8. **Fill the rect sensibly**: content bounding box covers ≥ 70 % of rect width and ≥ 60 % of
   rect height; margins balanced (left vs right margin differ by < 12 % of width).
9. **Canvas independence**: no absolute numbers tuned to one canvas; derive sizes from rect.w /
   rect.h (e.g. `u = Math.min(w, h)/100`).
10. **Bilingual**: labels may be Chinese, English or mixed; measure with ctx.measure, never assume
   a fixed char width.

## 5. Common config keys every view accepts

```
{"type":"view","kind":"...",
 "x":0,"y":0,"w":0,"h":0,            // optional rect (default = full canvas minus titlebar/credit)
 "title":"…","subtitle":"…",          // optional heading drawn by the view at top of rect
 "seed":7,                            // deterministic seed
 "period":28,                         // master loop seconds (focus rotation etc.)
 "log":{"who":"view","c":"acc1"}      // optional: emit log events
 ... kind-specific data ...}
```

## 6. Per-view brief (logic must be self-consistent)

- **nebula**: `nodes:[{id,label,group,weight?}]`, `edges:[{a,b,w}]` (w 0..1 strength),
  `groups:[{id,label}]`. Fixed force layout clustered by group (seeded, computed in build, then
  scaled to fit rect with margins), soft glowing halos per cluster, node radius by weight, edge
  width/opacity by w, slow drift, packets travelling along strong edges, one cluster "in focus"
  at a time (slow), group legend. Labels must not overlap (resolve in build: nudge or hide minor
  labels with a rule, not randomly).
- **timeline**: `lanes:[{id,label}]`, `events:[{lane,start,end,label}]` in abstract time units,
  `span:[t0,t1]`. A playhead sweeps left→right over `period` seconds; events before the playhead
  are done, the one under it is active (progress fill), later ones pending; lane labels left;
  axis ticks; dependency arrows optional `deps:[[from,to]]` routed between bars without crossing
  bars. Counters "done n/N" must match bars.
- **funnel**: `stages:[{label,value,sub?}]` values non-increasing (check() must report a violation),
  bar/trapezoid widths proportional to value, conversion % between stages = round(next/prev*100)
  from 1 % up and two significant digits below 1 % (0.025 %, never 0 %), particles flowing down
  whose density matches values, highlight sweeping stage by stage. Values ≥ 1 M print as `20M` /
  `1.5B`. Optional keys (as implemented): `period` (18), `scale` (`"linear"` default, `"log"` for
  data spanning orders of magnitude, say so in `credit`), `palette` (one accent per stage by
  default; `"mono"` = one quiet accent plus a hot accent on stage `focus`, default the last stage),
  `labelScale` / `valueScale` (1; multiply the label / value font size). Real-data example with
  `scale:"log"` + `palette:"mono"`: `examples/funnel-karpathy/`.
- **tree**: `root:{label,kind?,children:[...]}` (kind: agent|subagent|tool). Tidy tree layout
  (top-down, or left-right when the tree is deep and the rect is tall). Orthogonal rounded
  connectors. Animated expand/collapse **without layout jumps**: reserve space for all nodes; a
  subtree "collapses" by fading/greying its children & connectors and "expands" by lighting them
  in sequence; packets travel root→leaf along the active path.
- **ring**: `steps:[{label,desc?}]` (3–8) evenly on a circle, curved arrows between consecutive
  steps, a comet travelling the ring, current step highlighted (slow), centre shows the loop name
  and an iteration counter that increments exactly once per full lap; optional `spokes` / inner
  sub-loop. As implemented: `period` (28) = one lap, `name` (centre text, defaults to `title`),
  `innerLoop:["think","tool",...]` (inner sub-loop items, lit one per 1.2 s while step
  `innerLoopStep` (default 1) is current).
- **kpi**: `cards:[{label,value,unit?,delta?,series:[numbers],status?}]`, grid auto-chosen by count
  and rect aspect; each card: label, big number (title font), delta coloured ok/bad, sparkline of
  series with a moving cursor whose y equals the shown value at that time (one truth), status dot.

## 7. How to verify (must pass before you finish)

```
CHROME=$(command -v chromium || command -v google-chrome || find / -name chrome-headless-shell -type f 2>/dev/null | head -1)
python3 scripts/verify_view.py --config examples/<kind>/config.json --chrome "$CHROME" --out /tmp/vv-<kind>
```
verify_view.py renders the config in all 6 combos (3 canvases x 2 themes), runs check_frames
(--repeat) on each, the rule checks above, and writes 3 screenshots per combo + report.json.
Exit 0 = pass. Do NOT render mp4 (render.py) — the orchestrator does that. Keep Chrome runs few:
the machine has 2 CPUs shared with others.

## 8. Core notes (as implemented in assets/template.html)

- `impl.build(ctx)`, `impl.seek(t, ctx)`, `impl.events(lo, hi, ctx)`, `impl.check(ctx)` are all called with
  `this === impl`, which is shared by every view of that kind. Return the view's state from `build`;
  the core keeps it per view and passes it back as `seek(t, ctx, state)` (also `ctx.state`). Never keep
  per-view state on `this` or in module variables, or two views of one kind overwrite each other.
- Loops: every periodic motion must complete a whole number of cycles in the view's `period`, and
  `canvas.duration` should be a multiple of it, so the mp4 repeats without a jump.
- `ctx.measure(text, px, font?, bold?)`, `ctx.fit(text, px, maxW, font?, minPx=11, bold?)` -> `{text, size}`.
- `ctx.dark` is true unless `theme.preset == "light-pastel"`. `ctx.TH.titleFont` is a full CSS font stack
  (Smiley Sans first when `theme.titleFont:"smiley"`); in CSS use `var(--font-title)` / `var(--font)`.
- The view root is appended to the stage in config order *before* fonts are ready; `build` runs after
  `document.fonts.ready`, so measuring text in build is reliable.
- Hidden nodes (`display:none`) are skipped by the layout checker, so show/hide in seek is safe.
- The checker treats every `mark`ed 'box' pair as a potential overlap: do not mark decorative halos or
  glows as 'box'; mark only the cards/nodes that must not touch.
