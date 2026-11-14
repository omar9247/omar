# Showcase scenarios

The console can run four deliberately bounded story cards from the **Showcase** view. Every
reading is generated data and is labelled `provenance: simulated`; these cards are for showing
how the existing ingest, baseline, threshold, alert, stale-sensor, and timeline paths behave.
They are not crew measurements, diagnoses, or guarantees that an alert will fire.

## Catalog

`GET /showcases` returns a bare array of the four cards and their current lifecycle state. The catalog is fixed:

| Name | Reserved crew | Story | Mission-day timing |
|---|---|---|---|
| `normal` | `demo_normal` | Seed-12 ordinary variation with no injected scenario effect | Daily baseline days 1–14; weekly labs need 28 days; then normal variation |
| `co2_creep` | `demo_co2_creep` | Existing CO₂, reaction-lapse, and mood effects | Effects begin on day 22 and ramp for the configured eight days |
| `sleep_debt` | `demo_sleep_debt` | Existing sleep duration, efficiency, HRV, lapse, and mood effects | Effects begin on day 22 and ramp for the configured five days |
| `sensor_loss` | `demo_sensor_loss` | Existing dropped-sensor behavior for resting heart rate and RMSSD | Those readings stop from day 22; stale status follows the contract interval |

The simulator stores onset as zero-indexed day `21`; the API and cards correctly describe that as
**Mission day 22**. The catalog's `expected_events` are timing guidance only. Exact bands and
alerts remain owned by the existing rules, baselines, model availability, and generated values.

## Start and monitor a showcase

Start a card with its fixed reserved crew ID selected by the server:

```bash
curl -X POST 'http://localhost:8000/showcase/co2_creep?speed=1'
```

The response includes `name`, `crew_id`, `days`, `speed`, `simulated`, `label`, `provenance`,
`status`, and `progress`. `speed` is seconds per simulated day and is bounded to `0.1`–`60`
seconds; the default is one second. A caller cannot provide an arbitrary target crew. The server
always uses seed `12` and the corresponding `demo_<name>` crew.

Poll the catalog while the replay runs:

```bash
curl http://localhost:8000/showcases
```

Each card reports `state` as `ready`, `running`, `completed`, or `error`, with
`completed_days` and the additional `progress.day`, `progress.days`, and `progress.fraction` fields.
Starting the same card again while it is `running` returns HTTP `409`. Once it is `completed` (or
has errored), it can be safely started again; only that card's reserved demo crew is reset.

## Safety boundaries

A showcase reset atomically claims its demo crew ID in a small persistent SQLite ownership table and retains games. If that ID already contains non-showcase readings or game data, start returns HTTP `409` without resetting anything. Ownership survives a core restart, so known demo crews can be replayed safely. The additive table is created without deleting or migrating existing records. It does not
clear or overwrite `cm1`, `cm2`, or any other existing crew, and it preserves stored game
sessions. It does not alter the mission preset. Generated messages go through the same validated
`ingest` function as the existing scenario endpoint, and statuses use the normal core domain and
model-service path. The original `POST /scenario/{name}` behavior and its caller-supplied crew
remain unchanged.

The frontend can call `GET /showcases`, start a card, switch to the returned `crew_id`, and use
its existing status/timeline views. A progress card should describe an alert as “possible” or
“not guaranteed”, rather than presenting the simulation as an exact alarm script.
