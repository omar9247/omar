# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- **Astronaut (primary).** One crew member on a long mission, checking in on their own health between tasks. Their job: know how they are, what changed, and what to do now, without a doctor reachable in real time.
- **Crew medical officer (second).** A crew member who looks after the whole crew. Their job: see who needs attention and why, then open that person's view. One click away from the astronaut view, not the landing view.
- **Flight surgeon on the ground.** Receives health reports after the mission's communication delay (FR-16). Secondary; no dedicated screen planned.

## Product Purpose

AURA-Bio monitors each astronaut against their own personal baseline and raises an alert when several body systems drift together, before any single value turns red. It exists because health decline in space is usually multi-system (sleep, stress, immune, cardiovascular move together) and a monitor that checks one value at a time reacts late. Success for the hackathon: a new viewer can state the astronaut's status within 5 seconds (NFR-8), and one scenario is told end to end (CO₂ creep, sleep debt, deconditioning).

## Positioning

Cross-system pattern detection against a personal baseline: alerts name the signals from several body systems that moved together, with the cited response for the crew and for the medical team. Other entries for this challenge show baselines, single-value rule alerts, a body view and a delay mode; none connect systems.

## Operating Context

- Seen mostly as a live demo on a laptop or projector (judges watching a scenario replay, read at a distance, story in 2–3 minutes) and as recorded video and screenshots on the submission page. Phone use is not a judged path.
- Data arrives continuously (WebSocket push per reading); a scenario replays about one simulated day every few seconds. The first 14 days build the personal baseline (weekly labs: 28 days) and show no bands yet.
- Mission presets change the context: station (real-time ground contact), Moon (~1.3 s), Mars transit and surface (minutes of delay, so alerts read "follow onboard protocol; report queued").
- Daily check-in by the astronaut: a 90-second reaction test, mood, exercise.

## Capabilities and Constraints

- Backend (core service) owns all health logic; the web console is static HTML/CSS/JS served by it at `/` (no build step, works offline, vendored Chart.js 4.4.1 and fonts in `web/static/vendor`). The adapter at the top of `web/static/app.js` maps `/crew/<id>/status` onto the UI.
- Data per crew member: 15 signals in 6 systems (cardiovascular, neurocognitive, immune, bone & muscle, environment/radiation; metabolic has no signal yet), each with a band (green, amber, red, stale = overdue, unknown = no rule or no data), personal baseline, limits, provenance; alerts per episode (cross-system pattern or a signal red by a *published* limit) that stay until acknowledged; an anomaly score from a model (research concept); an immune-risk score (placeholder weights); mission preset; trends per signal.
- Requirements that bind the UI: FR-6 every alert shows reason, citation, response for crew and medical team; FR-7 body map with the status of six systems; FR-8 a late signal is never shown green; FR-10 every signal labelled real / replayed / simulated; FR-11 trend with baseline band and thresholds; FR-12 daily check-in; FR-13 preset switch changes delay, dose rate and alert wording; FR-17 crew overview; NFR-7 works offline; NFR-8 status in 5 seconds; NFR-10 no diagnosis, not-a-medical-device statement visible; NFR-11 all crew data simulated.
- Terminology: band words are RED / AMBER / WITHIN LIMITS / DATA OVERDUE / NOT MEASURED; thresholds are tagged "published" or "proposed"; "pattern" means a cross-system pattern.
- Demo-only controls: manual scenario replay replaces the selected crew member’s readings/alerts but retains games. Safe showcase replays instead use dedicated demo crew IDs and preserve existing crew data.

## Brand Commitments

- Name: AURA-Bio. The body map stays (FR-7). The requested 2026-11-14 enhancement enlarges it into a clickable web-sourced silhouette beside urgency and onboard actions; the full mission timeline remains below.
- Direction chosen by the team for the 2026-11-14 redesign, in their words: "Calm instrument: quiet, precise, readable at a glance; dark by default, colour reserved for status, real typography, no glows." The previous film-HUD look (cyan glow, reticles, scan lines, mono everywhere) is retired. The silhouette and organ illustrations in `web/static/images` were made by a teammate and may be reused.

## Evidence on Hand

- Real NASA data in the loop: ISS cabin CO₂ (Environmental Data Application) and RadLab dose can be replayed (`provenance: replayed`); calibration sources in `data/SOURCES.md`.
- Thresholds, patterns, responses and citations in `contract/thresholds.yaml`, from the team research doc.
- Model validation numbers: `docs/model-handover.md`.
- Absent: no real crew data, no user research, no testimonials. Nothing may be presented as real crew data or as a diagnosis.

## Product Principles

1. Status before detail: the first thing on screen is a sentence a stranger can repeat.
2. Honest by default: every value says where it came from, every limit whether it is published or proposed, every score that it is a research concept.
3. Calm until it matters: alarm styling only for live, unacknowledged alerts; resolved and acknowledged things recede.
4. Connections are the product: when systems move together, the screen shows the link, not just the parts.
5. Advice, never diagnosis: responses are suggestions with sources.

## Accessibility & Inclusion

WCAG 2.2 AA: contrast, keyboard operation of every control (including the reaction test and modals with Esc and focus handling), status never by colour alone, reduced motion respected. Must read from a distance on a projector.

## Requested console enhancement · 14 November 2026

The user requested a web-sourced human silhouette with six clickable, backend-colored system regions, visible urgency colors, light mode, larger text and Show more disclosure, tailored for an astronaut on a mission. Keep the calm dark default, add an explicit bright-ambient light theme and retain only the local preference. Use symbolic regions and a habitat frame, not diagnostic anatomy. Urgency, next actions, connection/save state and nonmedical/simulated-data labels must not be hidden. See `DESIGN.md` for the refined display tokens and interaction boundaries.

## Requested follow-up · complete silhouette, contribution pie and showcases

Use a different complete-body web vector without cropping anatomy, a pie/list of backend model contribution shares, and four curated simulated scenario walkthroughs. Keep the source figure whole, show model limitations beside the chart, and isolate showcase writes from existing crew records. No real-crew or clinical claims are added.

The contribution chart is optional detail: hide it until the user selects Show drift contributions, provide Hide drift contributions, and reset to hidden on each page load. No backend values, alarms or timeline behavior change.
