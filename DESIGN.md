# AURA-Bio console design

The console remains a calm operating instrument, served by the existing FastAPI core with vanilla HTML/CSS/JS. Public Sans and every required console asset are local. This refinement implements the requested interactive web-sourced silhouette, urgency colors, larger type, progressive disclosure and light mode; it does not replace the backend, timeline or games.

## Astronaut operating priorities

Keep status, current crew, mission day, ground delay, connection state and next onboard actions visible. Use static red and amber alarms with written levels, never flashing animation or color alone. Alerts retain their backend reason, cited crew response, medical-team response, mission wording and acknowledgment. Resolved and acknowledged episodes recede; acknowledgment does not mean resolution. Long explanations and citations use native Show more sections. Nonmedical, simulated-data and game-save/offline statements remain visible.

Alarm cards carry the corresponding backend red/amber background hue in the sidebar, system detail and alert dialog. Active cards use 14% hue, hover 20%; resolved-to-review cards use a quieter 8% tint, hover 12%. Secondary text is derived from the urgency text and foreground tokens, not washed-out gray. Acknowledged cards are neutral. Severity and active/resolved/acknowledged labels remain distinct in both themes; historical urgency does not imply an active alarm.

The body selector and onboard-action column lead into a full-width mission timeline. Each of six regions has an equivalent named button and Enter/Space operation. The complete CC0 Openclipart silhouette remains intact beneath symbolic system overlays; there is no clipping, masking or cut-away anatomy; habitat/radiation is a frame around the body, not an organ. Region mappings are symbolic selectors. Immune function is body-wide; bone/muscle currently uses exercise completion, not direct bone measurements. Metabolic remains not measured. No region implies anatomical diagnosis.

## Tokens and type

Dark is the default for low-light mission use: ground `#0f1216`, panel `#1a1e24`, ink `#e6e1d5`; red `#e5574f`, amber `#e0a33a`, green `#3fb27f`. Light mode is an explicit display choice for brighter ambient conditions: ground `#f1f2ef`, panel `#ffffff`, ink `#182321`, red `#ba302b`, amber `#976000`, green `#18744b`. Each theme has separate high-contrast status-text colors, muted ink, rules, focus and chart-baseline fill. Store only the local theme preference, with denied-storage fallback. Theme the charts and native controls as well as panels.

Body text is 17px, primary controls 16px with at least 44px height, explanatory copy 15–16px, fine-print and compact status labels 14–15px, section headings 19–20px, status headline 25px. Retain tabular numerals, restrained 1px rules, compact radii and no glow/film-HUD decoration. System state is color plus words; unknown is dotted and overdue is hatched/dashed. The backend supplies all bands, limits and responses.

## Disclosure and interruptions

Critical alert reason and crew response remain outside disclosure. Action evidence, medical response, sources, model scores and detailed signal limits may collapse. Preserve focus on system controls during telemetry updates and preserve open signal-limit disclosures. A visible connection-lost headline marks the remaining colors as last-known readings; do not desaturate away alarm urgency. Keep the canonical 90-second reaction test and its 355ms cutoff unchanged.

## Evidence boundary

Keyboard/browser checks and rendered dark/light review are engineering checks, not astronaut usability, flight certification, clinical validation or full assistive-technology testing. No new threshold, model calibration or measurement is introduced. Asset source and exact original checksum are in `web/static/images/SOURCES.md`.

## Drift contributions and showcase follow-up

The pie chart uses only the backend winning detector’s returned per-parameter terms, normalized for rounded display, with every parameter and zero share retained in a readable named list. Its categorical palette is separate from urgency; model detector/score, simulated provenance and not-causal/not-clinical framing remain visible. Missing, invalid, unavailable and all-zero output never becomes an equal-share pie. Parameter labels and slices can open the existing signal trend; theme changes retain the chart and its exact data.

Drift detail starts hidden on every page load. An explicit Show drift contributions button reveals the pie, named shares and explanation inline; Hide drift contributions collapses them again. The native button exposes expanded state and its controlled content. Telemetry and theme changes do not reopen a hidden chart; reopening renders the latest backend output. Urgency, actions and the timeline remain outside this optional detail.

Showcase is a console view, not a new app. Four existing seed-12 simulations have mission stories and what-to-watch guidance: normal flight, cabin CO₂ creep, sleep debt and sensor loss. Starts select a dedicated reserved demo crew, retain other crew readings/games and the current global mission preset, then show the real backend timeline, alarms and model chart. A visible demo banner links the scenario guide and offers return to the previous crew. Progress is explicitly refreshed, and an already-running scenario cannot be started again. No new calibration values or detector weights are introduced.
