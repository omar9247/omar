---
version: 1
slug: "web-static-index-html"
primary_target: "web/static/index.html"
related_targets: []
---

# Surface: AURA-Bio console (web/static/index.html)

Scope: the whole web console (every view: My health, Signals, Check-in, Crew overview, Ground reports, Mission panel, alert review, signal trend). Mode: Operate. Primary user: the astronaut; crew medical officer second. Judged on a projector and in recorded video.

Task: in five seconds, know the astronaut's status, what changed and what to do; then review alerts, open a signal's trend, take the daily check-in, switch crew, switch mission preset.

Constraints: status, bands, alerts and responses come from the core; nothing diagnostic; every value labelled with its provenance; limits tagged published or proposed; offline (vendored fonts and Chart.js); WCAG 2.2 AA.

## Direction contract

THESIS: Health as a mission timeline in mission days: one lane per body system, so systems drifting together line up vertically and the moment they moved together is drawn as a bracket. Refuses the category default of a KPI tile grid with separate charts and a glowing body hero.

OWN-WORLD: Flight-plan paper translated to a dark calm instrument: ground #0F1216, panel #1A1E24, ink #E6E1D5, ruled grid #2A2F37; colour only for status (amber #E0A33A, red #E5574F, green #3FB27F); one workhorse sans (Public Sans) with tabular numerals; 1px rules, 4-6px radii, no glows, no side stripes, no emoji.

STORY: The viewer reads the status sentence (band word, what drives it against the personal baseline, what changed and when, the preset's next action), sees on the timeline which systems moved and on which day, follows the numbered steps, and can acknowledge alerts or start the check-in.

FIRST VIEWPORT (refined 2026-11-14 by explicit user request): Top bar with view tabs and crew, mission, delay, day. Full-width status band: band word chip, one-sentence headline, Review alerts and Start check-in. Main: a readable web-sourced silhouette and six equivalent system buttons beside urgency-colored alarm review and next onboard actions; a full-width six-lane mission timeline below with baseline days shaded, today marked and pattern brackets. Long explanations, citations and research scores use Show more; actions and urgency remain visible. Light mode uses the same semantic vocabulary. Footer: not-a-medical-device statement, baseline note, live/connection state.

FORM: Flight Plan Timeline, grounded candidate 1 of 7 (impeccable's pick, chosen by the user). seed:133797336be15447

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

Refinement authority: `DESIGN.md`. Source asset: `web/static/images/SOURCES.md`. No change to health thresholds, mission responses, check-in timing or game behavior.

Follow-up: complete CC0 Openclipart silhouette under uncut overlays; full-width backend contribution pie/list before the existing timeline; a safe Showcase view with four reserved-crew replays and visible return/context. Model contributions explain detector terms, not physiological causation. All incumbent status/action/theme/offline rules remain binding.

Requested disclosure refinement: the drift pie/list and explanation start hidden and appear only after Show drift contributions. The same accessible button hides them again; telemetry, theme switching and reload never open them without a request.
