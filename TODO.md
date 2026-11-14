# Integration outcomes

- [x] Preserve the backend-served calm timeline console and existing 90-second reaction check-in; import only the newly published game bundle, not the retired main/frontend UI.
- [x] Store completed sessions for the selected crew using six known game IDs, UUID retries, bounded finite raw performance and mission time. Keep game records out of canonical health readings, alerts, baselines and anomaly scoring. Preserve game history during demo replay; delete it on explicit crew deletion.
- [x] Export once through the shared completion hook without changing game visuals, scoring or timing; namespace browser game databases per crew. Rebuild both runtime archives reproducibly from committed source.
- [x] Launch the hub from Check-in with visible saving consent/context, show recent raw sessions, and retain unsent results with visible manual retry. An actual browser Speed Click round saved through Python → JS → core; a round with the core stopped was retained for manual retry.

- [x] Connect saved capture/stdin/optional ESP32 serial to the existing contract MQTT topics with QoS 1 acknowledgements, seven Wokwi-contract signals, preserved crew/time/source/provenance, visible invalid/delivery failures and no retained health readings. Verify synthetic bridge transport, duplicates, WebSocket/timeline delivery, restart persistence and queued delivery; compile both firmware environments and all three custom chips.
- [x] Port the finalized anomaly model and separate baked deployment image without importing the model branch's old UI or changing calibrated values. Use shared blended first-14-calendar-day normalization only for model inputs, missing=0 and cap=8; leave persisted health baselines/rules/charts unchanged. The supplied build script created missing default seed-0 artifacts locally; no redesign/tuning or registry pull was performed.
- [x] Verify the exact combined broker/core/model stack: direct-container score parity, rule continuation during model failure and score recovery, six raw game contracts with idempotence/crew-time separation, health/model isolation, core/game persistence, replay-preserved games and explicit isolated crew deletion. Full merged regression: 148 passed, 1 local-artifact test skipped; standalone model runtime: 43 checks passed.

- [x] Make the published game runtime load from local assets on a cold launch with public internet requests blocked, preserving gameplay and crew/game-save behavior; keep the local core/server requirement explicit. All required browser resources loaded same-origin under enforced CSP/no-store, a public-fetch negative control was blocked, and one actual Speed Click round saved its matching UUID/crew/mission time. Health stayed at 424 readings/0 rejects. Final regression: 149 passed, 1 skipped, 1 existing warning.
- [x] Execute the actual Wokwi firmware and three custom-chip circuit, capture genuine Serial output and validate the seven-signal/default/daily/weekly contract. Defaults: 125 valid readings over 35 days/five lab days, zero failures; exact Serial → MQTT → isolated core persistence and duplicate replay passed. A second original-ELF run produced 117 valid readings, four pulse-off days, CO2 at 6.5 mmHg and pulse recovery, zero failures. Include only the tested firmware component and refreshed chip WASM, not its branch's older UI.

Hardware and game component PRs #1 and #2 remain open and unmerged. The combined branch contains both components and the finalized model port, preserving the backend console.

Not verified: physical serial device capture/flashing/calibration, real crew/clinical validation, production auth/TLS, mobile or assistive-technology testing. Games need a reachable local AURA-Bio server, not public internet or a warm CDN cache. Wokwi itself still requires its online service and a CI token. See `docs/offline-and-wokwi-verification.md` for actual evidence and setup boundaries.

## Astronaut console enhancements

- [x] Use a human silhouette vector sourced from the web, with its license and provenance recorded and the asset served locally for offline use.
- [x] Make alarms visible by color-coding urgency levels, retaining text labels, alert state, reason, crew and medical responses, citations and acknowledgment.
- [x] Add light mode alongside the existing dark mode, including charts, dialogs and status states; retain the display preference when local storage is available.
- [x] Make each symbolic silhouette region represent a system and be clickable and keyboard-operable, opening the corresponding signals and detail. Habitat/radiation represents the surroundings, not an organ; metabolic has no signal.
- [x] Change corresponding silhouette-region colors using the backend system bands; unknown and overdue data must not appear green.
- [x] Increase text size and put longer explanatory text inside Show more sections, without hiding urgent alarms, crew actions, offline/save messages or research/nonmedical labels.
- [x] Tailor the UI/UX for an astronaut on a space mission: readable controls, mission day/time and ground delay, calm non-flashing urgency, immediate onboard actions and honest simulated-data framing; preserve timeline, check-in and offline games.

## Complete silhouette, drift contributions and showcase scenarios

- [x] Find and use a different web-sourced full-body silhouette without cropping or removing anatomy. Preserve the whole vector beneath symbolic clickable/status-colored system overlays, source attribution and offline-local serving.
- [x] Create a pie chart representing each model parameter's share of the backend drift/anomaly detector terms. Show all returned parameters with named percentages, detector/score context, missing/model-unavailable and zero-contribution states; do not invent weights or imply medical causation.
- [x] Create readily accessible showcase scenarios with story/expected functionality and repeatable simulated replay, using dedicated demo crew IDs rather than replacing existing crew readings or saved games. Keep existing scenario definitions, thresholds, model and mission behavior intact.

Follow-up verified: 160 tests passed, 1 existing skip; all four actual 40-day demo replays completed. Original CM2 status/timeline/424 readings/7 games unchanged. See `docs/drift-and-showcase-verification.md`.

- [x] Show the drift contribution chart only after the user requests it. Start collapsed on each page load, provide an accessible show/hide button, and keep backend shares, trend links, theme support and model-unavailable messaging intact when opened. Three focused Python checks and their Node UI/delayed-response assertions passed; actual Enter/Space opening, click hiding and fresh-document reset verified.

- [x] Highlight alarm cards with their backend urgency hue in both themes. Retain red/amber labels, use a weaker tint for resolved-to-review episodes and neutral acknowledged cards, and preserve readable text, hover/focus and alert actions. Three focused tests passed; 28 DOM-only theme/state/text-contrast checks passed with a minimum 4.92:1, alongside actual dark/light card inspection.
