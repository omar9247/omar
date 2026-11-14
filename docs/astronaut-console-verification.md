# Astronaut console enhancement · 14 November 2026

All seven requested frontend enhancements are implemented in the existing FastAPI-served `web/static` console on `integration/full-stack`. The backend, health rules, model, firmware and arcade runtime are unchanged. PR #3 remains open and unmerged against `backend`.

## Delivered interface

The body selector uses the genuine public-domain Wikimedia **Human body silhouette.svg**, served locally. The original SHA-256 is `d0e37b1a7b06c9db1e4c822c3b5189f3d9da4335cd2c543d04ec2e255ed49f9e`. The interactive derivative preserves its exact path and translation as clipping geometry. Source and license details are in [the asset record](../web/static/images/SOURCES.md); the [source page](https://commons.wikimedia.org/wiki/File:Human_body_silhouette.svg) records the public-domain release.

Six symbolic regions and equivalent named buttons open system readings, baseline, provenance, rule limits, reading time and signal trends. Head represents neurocognitive monitoring, chest cardiovascular, upper torso immune labs, limbs bone/muscle monitoring, abdomen the unmeasured metabolic system, and the outer frame habitat/radiation. These are navigation regions, not diagnostic anatomy. Immune function is body-wide; bone/muscle currently uses exercise completion, not direct bone measurements. Unknown and overdue states are never converted to green, including partially unknown combined habitat/radiation state.

Alarms use static red and amber urgency with words and explicit active/resolved/acknowledged state. Higher-urgency active alarms sort first. Reasons and crew responses remain visible; medical responses and sources use native Show more. Earlier episodes retain full detail and acknowledgment. An open alert dialog refreshes when status changes, preserving open disclosure and review focus; Close remains available while scrolling. Acknowledgment remains distinct from resolution.

Light mode and the calm dark default use coordinated tokens for panels, controls, system regions, status, dialogs, timeline and charts. Preference persists locally, with a storage-denied fallback. Body text is 17px, primary controls 16px and at least 44px high; longer explanations, research scores and limits use Show more. Mission day, ground delay, connection state, onboard actions and simulated/nonmedical framing remain visible. The full mission timeline, 90-second check-in and offline game/save workflow are preserved.

## Actual checks

The complete regression finished with **151 passed, 1 skipped and 1 existing Starlette/httpx deprecation warning in 99.82 seconds**. The skip is the existing local-trained-artifact check; the previously built model container was not retrained or rebuilt. New tests cover exact web asset/path provenance, six keyboard-enabled regions, band precedence, unknown/overdue data, urgency ordering, escaped text, response disclosure, live-dialog refresh, per-signal simulated labels and storage-denied theme switching. Existing PVT deadline, game outbox and vendored runtime checks pass. After the final small no-data action wording and visible safety-framing refinements, the two focused console checks passed again.

The actual browser viewport was **1280 × 1100 CSS pixels**. The tool's saved viewport screenshots are scaled to **893 × 768 pixels**, not mobile screenshots. There was no page horizontal overflow on My health or Check-in. All six named controls opened the matching detail. Actual Enter selected the head region and Space selected the chest region; Escape closed the alert dialog without acknowledgment. Theme survived navigation. A sleep-efficiency chart retained the backend value, baseline and proposed limits while its line and baseline-fill colors changed between themes.

A clearly identified **browser-only state fixture**, with no API writes, exercised red, amber, green, overdue and unknown regions, red/amber alarm surfaces, active-to-resolved dialog updates and open disclosure retention. The original status was restored immediately. This is UI state verification, not additional health telemetry or clinical testing. The real preview's existing resolved alarms remain labeled resolved; they were not reactivated in the database.

Measured red badge text contrast is **5.46:1 dark** and **5.92:1 light**. The two themes' normal, muted, fine and status text on panel backgrounds exceed 4.5:1. This is a scoped token check, not a claim of complete WCAG certification.

The retained preview has **424 health readings, zero rejects, MQTT connected and seven saved game sessions**. Check-in still uses 90 seconds and 355ms, and its game link carries crew `cm2` and mission timestamp `2026-12-23T10:00:00+00:00`. No game round or telemetry scenario was repeated for this styling change. Preview was refreshed by copying only console assets into the existing core container; a normal future core build includes the committed assets. No volume or database was reset.

## Rendered evidence

[Dark-mode actual preview](verification/astronaut-console-dark.webp) and [light-mode actual preview](verification/astronaut-console-light.webp) show existing simulated crew data, not the browser-only fixture. [Structured browser check summary](verification/astronaut-console-evidence.json) records the interaction and preservation checks.

## Limits

No astronaut usability study, real crew/clinical validation, flight certification, full assistive-technology testing, mobile-device testing or new physical-hardware calibration was performed. The console and games still require a reachable local AURA-Bio server. Host-managed web-project diagnostics were unavailable for this non-managed FastAPI repository; JavaScript syntax checks, pytest/Node regressions and browser checks were used instead. Source code is saved to the existing GitHub integration PR, not migrated into a new React app or published as an always-on production service.
