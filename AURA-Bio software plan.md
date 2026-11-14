# AURA-Bio software plan

Nov 13, 2026 · @Shade · updated Nov 13, 2026 (data and model work, see 0)

AURA-Bio is astronaut health-monitoring software for the NASA Space Apps 2026 challenge "Create Health Monitoring Software for Astronauts on Space Missions". It scores each crew member's signals against their own baseline and alerts on patterns that span body systems. This plan covers a 48-hour build by six people on November 14–15.

## 0. Changes since the first version

| Section | Change |
| --- | --- |
| 1.2, 4.3 | Anomaly model: three autoencoders on 2-, 7- and 14-day windows instead of one short window |
| 4.1 | Resting heart rate defined as nocturnal (lowest 30-min mean during sleep) |
| 4.1, 4.2 | New signal `dose_mgy` (daily absorbed dose, per astronaut) and a model input; mission presets live in `contract/presets.yaml` |
| 4.4 | Dose rates and quality factors verified against the papers; radiation limits added |
| 4.7 | Data and model tooling added (uv, CPU PyTorch, pandas, scipy) |
| 5 | All datasets downloaded, processed and committed to the repo |
| 5.3 (new) | Which simulator values are calibrated from real data or papers, and which are documented assumptions |
| 6.2 | CO₂ creep and sleep debt now relative to each astronaut's or cabin's own baseline; sleep debt follows Van Dongen et al. 2003; expected results updated |
| 5.4 (new) | Real-data replay of ISS CO₂ and dose |
| 5.2, 5.3 | Weekly lab signals: lymphocytes, IL-6, NK activity, viral shedding; weak-data signals listed as not monitored |
| 6.2 | New immune dysregulation and solar particle event scenarios |
| 8.6 | DOIs added; Jones 2022, Basner 2011 and the immune/PVT/exercise sources added |
| 5.3 | Distribution shapes fixed so no signal piles up at a limit; BP person spread 10; every value marked sourced, estimated or assumption; CO₂ floor 0.76 mmHg; shedding 3%, NK 14%, lapse spreads |
| 5.3, 6.2 | Sleep, lapse and mood levels from ISS/PVT-B papers; sleep-debt mood effect −0.8 |
| 6.3 (new) | Model performance measured over 200 simulated astronauts per scenario |
| 5.3, 6.3 | Sleep duration and efficiency now vary together on normal days (r 0.59, BIDSleep); model re-measured |
| 5.3, 6.2 | Mood follows last night's sleep (Jones 2022 Table 1); sleep-debt mood drop now comes from that link (~−0.4) instead of a separate −0.8 |
| 5.3, 6.2 | Simulator validated against all real datasets; spreads matched by simulation; immune response size varies per astronaut (spread 78%) |
| 1.3 | Event dates corrected to Saturday 14 – Sunday 15 November |
| 8.6 (new) | Papers used for simulator values |

## 1. Overview

### 1.1 Problem and users

On long missions a crew cannot rely on real-time medical support from Earth. Health decline in space is usually multi-system: sleep loss, stress, immune change and cardiovascular change move together. A monitor that checks one value at a time reacts late.

| User | Need |
| --- | --- |
| Astronaut (primary) | Know how I am, what changed, and what to do now |
| Crew medical officer | See the whole crew and who needs attention |
| Flight surgeon on the ground | Receive health reports, delayed by distance |

### 1.2 Scope

| In scope | Out of scope |
| --- | --- |
| Simulated sensors and lab analyzers in Wokwi | Real hardware |
| Per-astronaut baselines, threshold bands, cross-system pattern alerts | Diagnosis or treatment decisions |
| One anomaly model (autoencoder on 2-, 7- and 14-day windows) and an immune-risk score | Validation against real crew outcomes |
| Flutter app: body map, alerts, trends, daily check-in | Modelling assay chemistry inside analyzers |
| Mission presets: station, Moon, Mars | Multi-vehicle or ground-station software |

### 1.3 Constraints

- **Time:** the event runs Saturday November 14 to Sunday November 15, 2026 (official Participant FAQ). Submission window: opens Saturday at 1:00 PM and closes Sunday at 1:00 PM local time (times to confirm with the local organisers) ([Space Apps 2026](https://www.spaceappschallenge.org/2026/)).
- **Data:** no open day-by-day astronaut vitals exist, so crew data is simulated and anchored to real NASA measurements (section 5).

### 1.4 Success criteria

The five criteria come from a secondary source ([Mindship](https://mindshipglobal.com/opportunities/nasa-space-apps-challenge-2026/)) and must be checked against the official guide.

| Criterion | Evidence we will show |
| --- | --- |
| Relevance | The astronaut is the main user; every screen answers status, change, action |
| Validity | Thresholds cited and tagged published or proposed; real NASA data in the loop; live demo |
| Impact | Multi-system decline caught early with no doctor reachable |
| Creativity | Cross-system pattern detection as the core idea |
| Presentation | One scenario told end to end; video and screenshots on the page |

### 1.5 Differentiator

Public repos for this challenge already show baselines, rule alerts, a body view and a communication-delay mode. AURA-Bio leads with one idea: it connects signals across body systems and warns before any single value is red. The immune-risk score is the example, the body map is the display, and the sensor layer proves the data path.

## 2. Requirements

Must items are Saturday work, Should items land Sunday morning, Could items only if time remains.

### 2.1 Functional

| ID | The system shall | Priority |
| --- | --- | --- |
| FR-1 | Ingest readings from sensors and analyzers over MQTT in the agreed message format | Must |
| FR-2 | Validate every message and reject malformed ones without stopping | Must |
| FR-3 | Keep a personal baseline for each astronaut and signal | Must |
| FR-4 | Classify each signal as green, amber or red using the research doc thresholds | Must |
| FR-5 | Detect cross-system patterns and raise one alert naming the signals involved | Must |
| FR-6 | Show each alert with its reason, citation and response for the medical system and the astronaut | Must |
| FR-7 | Show a body map with the status of all six systems | Must |
| FR-8 | Mark a signal stale when its reading is overdue | Must |
| FR-9 | Replay scripted scenarios with time sped up | Must |
| FR-10 | Label each signal as real, replayed or simulated data | Must |
| FR-11 | Show a trend per signal with baseline band and threshold lines | Should |
| FR-12 | Provide a daily check-in: reaction test, mood questions, food, fluid and exercise log | Should |
| FR-13 | Switch mission preset, changing delay, dose rate and alert wording | Should |
| FR-14 | Compute an anomaly score per astronaut from the autoencoder | Should |
| FR-15 | Compute the immune-risk score and show its inputs | Should |
| FR-16 | Queue a health report for the ground and release it after the preset delay | Could |
| FR-17 | Show a crew overview for the crew medical officer | Could |

### 2.2 Non-functional

Targets are proposed for the hackathon.

| ID | Quality | Requirement | Check |
| --- | --- | --- | --- |
| NFR-1 | Performance | A reading appears in the app within 1 second | Timed during a scenario run |
| NFR-2 | Fault tolerance | A malformed message or failing rule never stops processing | Send bad messages on purpose |
| NFR-3 | Recoverability | A killed service is back within 10 seconds with no stored data lost | Stop each container mid-scenario |
| NFR-4 | Graceful degradation | Rule-based alerts continue when the model service is down | Stop the model container |
| NFR-5 | Correctness | Every threshold and pattern has a boundary test; scenarios give the same alerts every run | Automated tests |
| NFR-6 | Explainability | Every alert shows the signals, values and source behind it | Review each alert screen |
| NFR-7 | Autonomy | Core functions work with no internet and no ground link | Run the demo offline |
| NFR-8 | Usability | A new viewer can state the astronaut's status within 5 seconds | Test on someone outside the team |
| NFR-9 | Portability | One app codebase for web and Android; backend starts with one command | Fresh laptop test |
| NFR-10 | Safe wording | No screen states a diagnosis; a not-a-medical-device statement is visible | Text review |
| NFR-11 | Privacy | Crew data is simulated; only public datasets are used | Data inventory |
| NFR-12 | Maintainability | Thresholds and patterns live in a config file, not code | Change one threshold without touching code |
| NFR-13 | Traceability | Every threshold links to its source and its published or proposed tag | Spot-check against the research doc |

## 3. Architecture

### 3.1 Styles

| Style | Where | Why | Trade-off |
| --- | --- | --- | --- |
| Publish-subscribe | Sensors and generator publish to MQTT; core service subscribes | Publishers are interchangeable and independent of the backend | Broker must be running; flows are harder to trace |
| Pipes and filters | Reading pipeline inside the core service | Each step is small and testable | A slow step delays those behind it |
| Layered | Core service code: API, domain, data | Health logic is testable without network or database | Extra boilerplate |
| Service-based | Core and model as separate containers | A model crash cannot stop alerts | One more service to run |
| Client-server | App to core over REST and WebSocket | Simple and well supported in Flutter | App depends on backend, so it caches last status |
| Rule-based | Thresholds and patterns as data, one engine | Explainable and traceable to citations | Cannot learn; the autoencoder covers that |

### 3.2 Views

The views follow the 4+1 model, with decomposition views added under the logical view.

| View | Question | Diagrams |
| --- | --- | --- |
| Context | What is inside and outside the system? | 3.3 |
| Scenarios | Who uses it and for what? | 3.4 |
| Logical and decomposition | What are the parts? | 3.5: modules, functions, layers, data; 7.1: work |
| Process | What happens at run time? | 3.6: sequence, pipeline, states |
| Physical | What runs where? | 3.7 |

### 3.3 Context

&#91;embedded content: system context · 3 input channels, 1 backend, 1 app\]

Wokwi and the scenario generator publish identical messages, so either can drive the system.

### 3.4 Scenarios

&#91;embedded content: use-case diagram · 4 actors, 6 use cases\]

The astronaut's three use cases are built and demonstrated first.

### 3.5 Decomposition

**Modules.** What is built, and what each subsystem contains.

&#91;embedded content: module decomposition · 6 subsystems\]

Each subsystem maps to one workstream in section 7. The shared contract is owned jointly and changed only by agreement.

**Functions.** What the system does, independent of how it is built.

&#91;embedded content: functional decomposition · 3 functions, 12 sub-functions\]

Every functional requirement belongs to one branch. FR-9, scenario replay, supports testing and sits outside the tree.

**Layers.** How the core service and app are divided by responsibility.

&#91;embedded content: layer decomposition · 4 layers\]

Each layer calls only the one below it. All health logic is in the domain layer.

**Data.** What is stored.

&#91;embedded content: data decomposition · 7 tables\]

Arrows point from the one side to the many side. Threshold and Pattern load from the config file; a pattern refers to thresholds by signal name.

### 3.6 Process

**Sequence of one reading.**

&#91;embedded content: sequence diagram · 6 participants, 10 messages\]

Solid arrows are calls, dashed arrows are replies. The model call is optional: alerts are sent even if it fails.

**Reading pipeline in the core service.**

&#91;embedded content: flowchart · 8 steps, 3 decisions\]

Each box is one function with its own tests.

**States of one signal.**

&#91;embedded content: state machine · 4 states for one signal\]

Any state falls to Stale when a reading misses its expected interval (FR-8).

### 3.7 Physical

&#91;embedded content: deployment diagram · 3 containers, 1 volume, 3 clients\]

The grey box is what one Docker Compose command starts. If Wokwi cannot reach the local broker, both publishers point at a public broker instead.

## 4. Detailed design

### 4.1 Signals

Thresholds are copied from the research doc. Most are relative to a personal baseline, so each simulated astronaut gets a baseline period before any scenario runs.

| System | Signal | Source | Amber | Red |
| --- | --- | --- | --- | --- |
| Cardiovascular | Resting heart rate | Wokwi chip | +10 bpm over baseline | +20 bpm with symptoms |
| Cardiovascular | HRV (RMSSD) | Wokwi chip | Down more than 20% | Down more than 35% |
| Cardiovascular | Blood pressure | Generator | Persistent deviation | Over 180 systolic or 120 diastolic |
| Neurocognitive | Sleep duration | Generator | 5 to under 7 h | Under 5 h |
| Neurocognitive | Sleep efficiency | Generator | 75–84% | Under 75% |
| Neurocognitive | Reaction-time lapses | In-app test | Up more than 20% | Up more than 40% |
| Neurocognitive | Mood and stress | In-app questions | Persistent decline | Severe distress |
| Environment | Cabin CO₂ | Wokwi chip | Above 2.5 to 3 mmHg | Above 3 mmHg |
| Radiation | Cumulative dose (from daily `dose_mgy`) | Generator | Near mission dose budget | Over authorised limit |
| Immune | Lymphocytes, NK activity, cytokines, viral PCR | Wokwi analyzer chip | Research doc 4.1 | Research doc 4.1 |
| Metabolic | Vitamin D, glucose | Generator | Research doc 4.5 | Research doc 4.5 |
| Mucosal | Salivary sIgA | Generator | Change over 25%, either direction | Change over 40% with symptoms |
| Bone and muscle | Bone density, turnover markers | Generator | Research doc 4.2 | Research doc 4.2 |
| Bone and muscle | Exercise completion | In-app log | 75–89% | Under 75% |
| Metabolic | Calories, fluid | In-app log | 75–89% of target | Under 75% |
| Metabolic | Body mass | In-app log | Loss over 2% | Loss over 5% |

Resting heart rate is the nocturnal value: the lowest 30-minute mean heart rate during sleep (Garmin-style; less noisy than a single lowest reading). Cabin CO₂ from NASA data arrives in ppm and is converted to mmHg (÷ ~1316 at 1 atm).

Radiation is published as `dose_mgy`, each astronaut's daily absorbed dose (personal-dosimeter style: every astronaut has their own level, independent of the others). The core service sums it and converts to dose equivalent (mSv) with the preset's quality factor for the limit check. Daily dose is also an anomaly-model input.

Three custom Wokwi chips are built: pulse, CO₂ and one analyzer. The generator publishes every other signal in the same message format. The sIgA trigger is two-sided because the research doc's own source shows it rising in flight.

### 4.2 Contract

One JSON message per reading:

```json
{
  "crew_id": "cm1",
  "ts": "2026-11-14T10:00:00Z",
  "signal": "cabin_co2_mmhg",
  "value": 2.7,
  "source": "wokwi",
  "provenance": "simulated"
}
```

- **Topics:** `aura/<crew_id>/<group>`, group is `vitals`, `cabin`, `radiation` or `labs`. QoS 1; the Wokwi ESP32
  publishes at QoS 0 (its MQTT library has no QoS 1), which the core service still receives.
- **Timestamp:** `ts` is ISO 8601 **with a time zone**, e.g. `Z`. A `ts` without one is rejected: it would be read
  as the server's local time and land hours off. Simulated sources send one `ts` per simulated day, starting
  `2026-11-14T10:00:00Z`.
- **Signal names** include the unit: `rmssd_ms`, `cabin_co2_mmhg`.
- **REST:** `GET /crew/<id>/status`, `POST /checkin`, `GET /health`. `POST /checkin` takes `ts` as optional: left
  out, the check-in lands on the crew member's current simulated day, which the app cannot know.
- **WebSocket:** one channel pushing status and alerts.

### 4.3 Evaluation logic

1. **Baseline.** Mean and spread per astronaut and signal over the baseline period. Later readings are expressed as deviations.
2. **Bands.** Each reading maps to green, amber or red from `thresholds.yaml`.
3. **Patterns.** The combined findings in section 7 of the research doc, expressed as rules over bands. One alert per match, with signals, citation and both response lists.
4. **Anomaly score.** Three autoencoders trained on normal days only, one per window length: 2 days (sudden change), 7 days and 14 days (slow drift). Input is the window of signals expressed as standard deviations from the astronaut's own 14-day baseline. High reconstruction error means the period does not look like this astronaut's normal. Each model's alarm line is where 99% of normal days score below it (about 1 false alarm per 100 normal days). The service returns the highest score, which window produced it, and each signal's share of the error.
5. **Immune-risk score.** A weighted sum of deviations in NK activity, T-cell function, sIgA, HRV, sleep, radiation dose and microbiome change. Weights are placeholders; the app labels the score as a research concept.

The autoencoders train on generated normal days whose levels, day-to-day spread and day-to-day persistence come from real data where available (section 5.3). They demonstrate the method and are not validated on crew data. All three share one architecture and one training script; no other model type is planned.

### 4.4 Mission presets

| Preset | One-way signal delay | Dose rate (absorbed) | Quality factor | Alert wording |
| --- | --- | --- | --- | --- |
| Station | Near real time | 0.285 mGy per day (RadLab DosTel mean, Jan–Mar 2022) | 1.85 (derived) | Contact the ground |
| Moon | About 1.3 seconds | 0.317 mGy per day (Chang'e 4, Zhang et al. 2020) | 4.3 | Contact the ground |
| Mars transit | Roughly 3 to 22 minutes | 0.48 mGy per day | 3.83 | Follow onboard protocol; report queued |
| Mars surface | Roughly 3 to 22 minutes | 0.21 mGy per day | 3.2 | Follow onboard protocol; report queued |

Presets live in `contract/presets.yaml`. Each astronaut's daily dose varies about 5.5% day to day (measured on the ISS and reused for the other presets) around their own level.

Mars dose rates are Curiosity measurements ([Hassler et al.](https://typeset.io/pdf/mars-surface-radiation-environment-measured-with-the-mars-244eildtx0.pdf)). The Station rate is a time-weighted daily average of real ISS detector readings (readings come more often inside the South Atlantic Anomaly, so a plain average would over-count to ~0.75 mGy/day). Quality factors are dose equivalent ÷ absorbed dose from the same papers (Mars: Zeitlin et al. 2013, 1.84 mSv/day in transit; Hassler et al. 2014, 0.67 mSv/day on the surface; Moon: Zhang et al. 2020, 1,369 µSv/day). The Station factor is derived (Zhang's lunar/ISS ratio of 2.6 against our measured ISS dose). Limits for the rules: 600 mSv career effective dose and 250 mSv per solar particle event (NASA-STD-3001). Delay figures are approximate and need a citation before the pitch.

### 4.5 Reliability tactics

The design contains each failure and recovers within seconds while alerts keep flowing.

| Tactic | Satisfies |
| --- | --- |
| Validate every message with Pydantic; log rejects and drop them | NFR-2 |
| Evaluate each rule inside its own error handler | NFR-2 |
| Run the model in a separate service; show the score as unavailable if it is down | NFR-4 |
| Docker restart policy on every container; state in SQLite | NFR-3 |
| MQTT QoS 1, persistent session, automatic reconnect | NFR-3 |
| Expected interval per signal; overdue shows as stale | FR-8 |
| App keeps last status, shows a reconnecting banner, resubscribes | NFR-3 |
| `/health` route and structured logs | NFR-2, NFR-3 |

### 4.6 App screens

| Screen | Content | Requirement |
| --- | --- | --- |
| Home (body map) | Six systems coloured by status; a line joins systems when a pattern fires | FR-7 |
| Alerts | What fired, why, citation, response for system and astronaut | FR-6 |
| System detail | Trend per signal with baseline band, thresholds and data label | FR-10, FR-11 |
| Daily check-in | 90-second reaction test, mood questions, logs | FR-12 |
| Crew overview | One card per astronaut | FR-17 |
| Mission panel (demo only) | Preset switch and scenario picker | FR-9, FR-13 |

Visual style: dark background, translucent body figure, thin glowing overlays, in the spirit of The Good Doctor. The figure is original or openly licensed art. Version one is a flat SVG with six tappable regions.

### 4.7 Tech stack

| Layer | Choice | Reason |
| --- | --- | --- |
| Sensor simulation | ESP32 in Wokwi, Arduino C++, custom chips in C | Simulates the ESP32 and its WiFi; chips cover parts Wokwi lacks |
| Messaging | MQTT: public test broker, Mosquitto in Docker as fallback | Decouples publishers from the backend |
| Generator | Python, paho-mqtt | Same language as backend |
| Core service | Python, FastAPI, Pydantic | REST, WebSocket and validation with little code; shares a language with the model |
| Storage | SQLite | No setup |
| Model | PyTorch (CPU build) autoencoders in their own FastAPI service | Trains on a laptop in about a minute per window length |
| Data processing | Python, pandas, scipy; uv for the environment | Reads the raw datasets once into small tables |
| App | Flutter with fl\_chart, flutter\_svg, web\_socket\_channel, Riverpod | One codebase for web and mobile |
| Packaging | Docker Compose | One command to start |

## 5. Data

All files are downloaded before the event into `data/` with their source recorded. Nothing depends on a NASA server during the demo.

Status: done. `data/fetch.py` downloads every source into `data/raw/` and records each file's URL and hash in a manifest; `data/process.py` turns them into small tables in `data/processed/`. Both raw and processed data are committed, so a plain clone works offline (about 90 MB).

### 5.1 Datasets

| Priority | Source | Provides | Used for | Status |
| --- | --- | --- | --- | --- |
| 1 | [NASA Environmental Data Application](https://visualization.osdr.nasa.gov/eda) ([API](https://visualization.osdr.nasa.gov/eda/api_reference)) | ISS CO₂ in ppm at 5-min cadence, 24 missions | Normal CO₂ level and spread | Downloaded (35 MB). Only 10 missions have usable CO₂; gap-fill runs and impossible values removed, leaving 423 clean days. Calibrates the simulator. Still to confirm: cabin air or inside the rodent habitat |
| 2 | [NASA RadLab](https://visualization.osdr.nasa.gov/radlab/gui/data-api) | ISS DosTel absorbed dose rate, Jan–Mar 2022 (DosTel data ends April 2022) | Dose signal, station preset | Downloaded (13 MB), daily dose computed. No ISS detector in RadLab reports dose equivalent. Calibrates `dose_mgy` |
| 3 | [Curiosity RAD](https://typeset.io/pdf/mars-surface-radiation-environment-measured-with-the-mars-244eildtx0.pdf) | Mars cruise and surface dose rates | Mars presets | Published values |
| 4 | [PhysioNet BIDSleep](https://www.physionet.org/content/bidsleep-dataset/1.0.1/) | 253 nights, 47 adults: heart rate and expert-scored sleep stages (accelerometer skipped) | Calibrating heart rate and sleep | Downloaded (38 MB, hash-checked), per-night metrics computed. Calibrates the simulator |
| 5 | OSDR Inspiration4: OSD-569, OSD-575 | Crew blood count, metabolic, cardiovascular and cytokine panels, 4 crew × 7 time points | Anchors for analyzer signals and immune-risk score | Downloaded (0.3 MB), tidy table and before/after-flight change computed (e.g. lymphocytes −27%, IL-6 +90% the day after landing). Not yet a simulator signal |
| 6 | [NOAA SWPC proton flux](https://www.swpc.noaa.gov/node/39) | 7 days of 5-minute proton flux | Optional solar particle event | Downloaded; the window holds no event (≥10 MeV peak 0.48, storm level starts at 10), so the solar scenario uses a published ISS event instead |

Priorities 1 to 4 are enough to state that real NASA data runs through the system. Datasets listed on the official challenge page take precedence over this list.

### 5.2 Gaps

Beat-to-beat HRV in flight, reaction-test results and mood have no open astronaut data. They are simulated from the findings in the research doc and published studies (5.3), and labelled as simulated in the app and on the project page.

Lab signals now simulated, one analyzer sample a week (rules and immune-risk score only, not model inputs): lymphocytes, IL-6, NK activity (% of own baseline) and viral shedding (yes/no). Not simulated, for lack of usable data: sIgA (rises in flight), vitamin D (falls), glucose, body mass (falls), calories (ISS crews eat 74–80% of recommended, already below the red line in 4.1) and fluid. The app should show these as "not monitored in this demo".

### 5.4 Real-data replay

`generator.publish --replay` streams real ISS measurements in place of simulated ones, labelled `provenance: replayed` (FR-10):

| Signal | Real source | Who gets it |
| --- | --- | --- |
| Cabin CO₂ | NASA EDA: RR-5 (60 days, default), RR-3 (45 days) or all 10 missions stitched in date order (423 days, with jumps between missions); `--co2-source` | Every crew member, every preset (ISS cabin stands in for any cabin) |
| Daily dose | NASA RadLab DosTel1 / DosTel2 (90 days each) | Crew member 1 and 2, station preset only; others keep simulated dose |

Everything else stays simulated. When a scenario changes a replayed signal (e.g. CO₂ creep), the effect is added on top of the real value from onset and those days are labelled `simulated`, because they are no longer real measurements. Days past the end of a real series are simulated. Message timestamps follow the demo timeline, not the original measurement dates. Replay is opt-in; tests and model training stay fully simulated.

### 5.3 Simulator calibration

| Signal | Level | Day-to-day spread | Person-to-person spread | Day-to-day persistence | Source |
| --- | --- | --- | --- | --- | --- |
| Resting heart rate | 60.1 bpm | 3.8 | 4.6 | 0.25 | BIDSleep (spreads matched by simulation) |
| Sleep duration | 6.5 h | 0.98 | 0.64 | −0.20 | Level: ISS astronauts (Jones et al. 2022); spreads: BIDSleep |
| Sleep efficiency | 91.8% (max 100) | 4.9 | 4.4 | −0.27; linked to same night's sleep duration, r 0.59 (BIDSleep) | Level: Jones et al. 2022; spreads: BIDSleep |
| Cabin CO₂ | 2.21 mmHg (min 0.76) | 0.56 | 0.39 (between cabins) | 0.87 | NASA EDA (spreads matched by simulation) |
| Daily absorbed dose (station) | 0.285 mGy | 5.5%, multiplicative | 0.026 (between detector locations; only 2) | −0.05 | NASA RadLab |
| HRV (RMSSD) | 55 ms (estimate; daytime ECG average ~42) | 17 ms, multiplicative | 15 | 0.4 (assumption) | Bellenger et al. 2022; Nunan et al. 2010 |
| Systolic BP | 117 mmHg | 9 mmHg | 10 (estimated: Ohasama's 13.4 covers ages 7–98 and gave systolic < 90 on 4.5% of days) | 0.4 (assumption) | Ohasama study |
| Reaction lapses | 7.5% of trials | 5.4 (derived) | 6.5 (estimated) | 0.4 (assumption) | Basner et al. 2011; PVT reliability ICC 0.59 |
| Mood (0–10) | 6.2 | 0.6 (assumption) | 1.7 (estimated) | 0.4 (assumption) | Jones et al. 2022 (in-flight stress ~38/100, converted) |
| Exercise completion | 98% (assumption) | 4 (assumption) | 2 (assumption) | 0.4 (assumption) | none; ISS crews log ~600 min/week, 168 ± 44 min aerobic (ENERGY study) |
| Lymphocytes (weekly) | 2,679 /µL | 10.1% | 23.9% | — | Inspiration4; Coskun et al. 2020 |
| IL-6 (weekly) | 3.7 pg/mL | 30% | 11% (matched by simulation) | — | Inspiration4; biological-variation studies (25–50%) |
| NK activity (weekly) | 100% of own baseline | 14% | — | — | TINKL study (123 adults); Bigley et al. 2019 for flight change |
| Viral shedding (weekly) | 3% of samples positive | — | — | — | Mehta et al. 2017 (healthy controls) |

Persistence and the night-to-night values for sleep and heart rate come from only 64 pairs of consecutive nights, so they are rough. Real cabin CO₂ wanders about 0.5 mmHg a day, so a slow CO₂ rise alone looks normal to the model. Signals that can't go below 0 (HRV, lapses, labs, dose) vary multiplicatively; sleep efficiency and exercise vary as a shortfall below 100%; mood varies on a logit scale between 0 and 10. None of them can pile up at a limit. Every value is sourced, estimated (derived, rough) or a documented assumption; the full list is in `data/SOURCES.md` ("Final status").

**Validation against the real data** (`data/validate.py`, also a test). Copying the raw spreads overstated the person-to-person spread, because a person's average over ~5 nights still carries day-to-day noise. The spreads marked "matched by simulation" were therefore tuned until simulated runs as long as the real ones reproduce the real statistics. Result, real vs simulated:

| Signal | Within-unit spread | Between-unit spread | Real values inside simulated 95% range |
| --- | --- | --- | --- |
| Resting HR (47 people) | 3.64 vs 3.57 | 5.28 vs 5.21 | 94.5% |
| Sleep duration | 1.01 vs 1.03 | 0.73 vs 0.75 | 96.4% |
| Sleep efficiency | 5.76 vs 5.78 | 4.71 vs 5.03 | 96.4% |
| Cabin CO₂ (10 missions) | 0.46 vs 0.46 | 0.50 vs 0.50 | 95.0% |
| Daily dose (2 detectors) | 0.016 vs 0.016 | 0.026 vs 0.026 | 97.8% |
| IL-6 (4 crew) | 1.04 vs 1.15 | 0.76 vs 0.77 | 100% |
| Lymphocytes (4 crew) | 1,333 vs 280 | 899 vs 656 | 91.7% |

Same-night link of sleep duration and efficiency (within each person): real 0.59, simulated 0.60–0.62. Mood follows last night's sleep on every day, using Jones et al. 2022 Table 1 as published (≤4 h −0.77 … 6–7 h −0.05 vs 7–8 h); a test checks the within-person effect reproduces those values. Other signals are not linked: resting HR shows no reliable link to sleep in the data (r −0.09).

Sleep levels differ on purpose (ISS values, not BIDSleep's ground nights). Lymphocyte spreads stay on Coskun et al. 2020: the 4 Inspiration4 crew were sampled months apart, which adds slow change a weekly sample would not show. Flight change (day after landing vs pre-flight): lymphocytes −26.8% real vs −26.5% simulated, IL-6 +90% vs +98%. All 4 crew fall inside the simulated 95% range, because each simulated astronaut gets their own response size (spread 78% of the average, as among the Inspiration4 crew: lymphocytes −48% to +2%).

## 6. Verification

### 6.1 Test levels

| Level | What | Covers |
| --- | --- | --- |
| Unit | One test just below and just above each threshold and pattern boundary | NFR-5, NFR-13 |
| Scenario replay | Each scenario script runs as an automated test and must produce the expected alerts | NFR-5, FR-9 |
| Fault injection | Bad messages, killed containers, model stopped, network off | NFR-2, 3, 4, 7 |
| Timing | Sensor-to-screen delay measured during a scenario | NFR-1 |
| Usability | Someone outside the team reads the home screen | NFR-8 |

### 6.2 Acceptance scenarios

These are also the demo. The generator runs at about ten seconds per simulated day.

| Scenario | Input | Expected result |
| --- | --- | --- |
| CO₂ creep | CO₂ rises 1.2 mmHg above the cabin's own level over 8 days; headache logged; reaction lapses up 25% | Environment amber then red; pattern "CO₂-associated performance impairment"; response: check ventilation. Caught by the rules, not by the anomaly model (score peaks at 0.9, below the alarm line of 1) |
| Sleep debt | Sleep falls 2.4 h below the astronaut's own baseline over five days; RMSSD down 25%; reaction lapses up 14 percentage points by day 14 and still rising; mood down about 0.4 points, through the everyday sleep–mood link (astronaut stress ratings by sleep length, Jones et al. 2022) | Anomaly score crosses the alarm line on day 4 (2-day window), day 7 (7-day) and day 9 (14-day); neuro and cardio amber; pattern "sleep-loss-related impairment". "Score rises before any band changes" is not yet verified against the rule engine |
| Deconditioning (exercise lapses) | Exercise completion drops to 70%; resting heart rate rises 12 bpm over 21 days; HRV down 10%. Sizes are this plan's proposal: on the ISS, resting HR stays flat when crew exercise (Hughson et al.); bed rest without exercise raises it | Cardio and musculoskeletal amber; pattern "cardiovascular deconditioning"; response: exercise review and ECG |
| Preset change | CO₂ creep replayed under the Mars transit preset | Same alert reads as onboard protocol with a queued report |
| Sensor loss | Pulse chip stops publishing | Heart rate and HRV show stale, never green |
| Solar particle event | On day 21 every crew member's dose is 51% higher for one day (+0.146 mGy on the ISS, as measured on 10 Sep 2017, Berger et al. 2018); other presets scaled by their own level (derived) | Radiation amber; cumulative dose steps up; dose is a model input, so the anomaly score can react |
| Immune dysregulation (90 days) | From day 21, over 60 days: lymphocytes −27%, IL-6 +90% (Inspiration4), NK activity −50% (Bigley et al. 2019); viral shedding in 23% of weekly samples (from 3%; NASA astronaut saliva data). Each astronaut's response size varies (spread 78%, Inspiration4 crew), applied on the log scale so no value goes below 0; averages unchanged | Immune system amber/red on the weekly lab values; immune-risk score rises. Lab values are not model inputs, so the anomaly score does not react |

### 6.3 Model performance

Measured over 200 simulated astronauts per scenario (`model.train` prints this); onset on day 21; "any" = highest of the three windows, as the service reports.

| Scenario | Flagged after onset (any window) | Median days to first flag | Best single window |
| --- | --- | --- | --- |
| Normal (false alarms) | 19% of astronauts over 20 days; 1.5% of normal days | — | 14-day: 1% |
| Sleep debt | 64% | 6 | 2-day: 61% |
| Deconditioning | 84% | 6 | 2-day: 82%; 7-day: 62% |
| Solar particle event | 97% | same day | 2-day: 97% |
| CO₂ creep | 32% (barely above normal) | 9 | caught by the rules instead |
| Immune dysregulation | 18% (= normal) | — | lab values are not model inputs; caught by the rules |
| Sensor loss | 14% | — | handled by stale marking (FR-8) |

After the final data calibration (realistic, skewed spreads for lapses and exercise; slow CO₂ drift), the 7- and 14-day windows lost sensitivity, and matching the spreads to the real data (5.3: more day-to-day heart-rate noise) cut sleep debt and deconditioning from ~77% to 64%. Adding the real sleep duration–efficiency link (5.3) and retraining moved them to 79% and 86%, with false alarms 1.1% → 1.4% of days; deconditioning does not touch sleep, so most of that swing is run-to-run variation from retraining on new random data, not the link. Treat single numbers as ±10–20 points. Linking mood to sleep (and dropping the double-counted −0.8 sleep-debt mood effect) then took sleep debt to 64% while deconditioning stayed at 84%, so that drop is real: sleep debt's mood change is now smaller and mood dips after short nights are normal. The plain mean-and-spread scaling against a 14-day baseline is thrown by heavy tails. A robust scaling (e.g. median and spread that ignore outliers) is the first thing to try when model work resumes.

## 7. Delivery

### 7.1 Work breakdown

&#91;embedded content: work breakdown · 5 workstreams, 25 packages\]

Each column is one workstream and maps to a subsystem in 3.5. The contract is the first package and blocks all others.

## 8. References

Licences were not checked for most repos. Confirm each before copying code.

### 8.1 Sensor layer

| Resource | Use |
| --- | --- |
| [Wokwi Custom Chips API](https://docs.wokwi.com/chips-api/getting-started) | Reference for every chip: JSON pin file plus C code; attributes give live sliders |
| [CD4051B chip walkthrough](https://blog.wokwi.com/custom-chips-cd4051b-analog-multiplexer) | Template for a chip with analog pins |
| [ESP32 MQTT basic on Wokwi](https://wokwi.com/projects/394246976272529409) | Starting sketch: Wokwi-GUEST network, PubSubClient, public broker |
| [ESP32 sensor to MQTT on Wokwi](https://wokwi.com/projects/341043726457504339) | Pattern for read, package, publish |

### 8.2 Model

| Resource | Use |
| --- | --- |
| [LSTM-based Autoencoder](https://github.com/Rajatsingh24/LSTM-based-Autoencoder) | PyTorch autoencoder that trains on a CSV; closest match to the planned model |
| [Recurrent-Autoencoder](https://github.com/PyLink88/Recurrent-Autoencoder) | Reference architecture for multi-sensor input |
| [anomaly-detection-toolkit](https://pypi.org/project/anomaly-detection-toolkit/) | Ready-made detectors as a fallback |

### 8.3 App

| Resource | Use |
| --- | --- |
| [muscle\_map](https://pub.dev/packages/muscle_map) | Tappable SVG body regions; maps muscles, so a code reference only |
| [PVT in PsychoPy](https://github.com/snipeso/pvt) | Timing and lapse counting for the reaction test |
| [circog](https://github.com/Til-D/circog) | Mobile reaction-test reference |

### 8.4 Other teams on this challenge

| Repo | Worth studying |
| --- | --- |
| [H.E.L.I.O.S](https://github.com/haXorFalcon/nsa) | Loading Inspiration4 panels into a telemetry feed |
| [AURORA](https://github.com/fabriciojunio/aurora-astronaut-health) | Per-person baseline rules with cited sources |
| [Crew Health Monitor](https://github.com/AdityaK0804/Crew-Health-Monitor) | Earth rules against space rules; mission presets |
| [Cosmic Shield](https://github.com/mahadindotnet/cosmic-shield) | Table mapping challenge themes to features |

### 8.5 Source documents

- Team research doc, "Nasa pre hackathon": biomarkers, thresholds, combined patterns, responses and their 38 references.
- [Space Apps 2026](https://www.spaceappschallenge.org/2026/) and [Participant FAQs](https://www.spaceappschallenge.org/resources/participant-faqs/): dates, team size, submission rules.
- [OSDR tutorials](https://osdr-tutorials.readthedocs.io/en/latest/pages/guides/radlab_portal.html): RadLab and Environmental Data Application guides.

### 8.6 Papers used for simulator values

DOIs marked * were taken from memory and should be checked when the paper is opened.

| Paper | DOI | Used for |
| --- | --- | --- |
| Van Dongen, Maislin, Mullington, Dinges 2003, *SLEEP* 26:117 | 10.1093/sleep/26.2.117 | Sleep debt: lapses +14 per 10-min test by day 14 in the 4 h group (curve t^0.78); sleepiness ~1 point of 7, levelling off (t^0.24), used as a mood proxy |
| Law et al. 2014, *J Occup Environ Med* 56:477 | 10.1097/JOM.0000000000000158 * | CO₂ and headache: odds roughly double per +1 mmHg; keep 7-day average below 2.5 mmHg |
| Barger et al. 2014, *Lancet Neurology* | 10.1016/S1474-4422(14)70122-X * | ISS crews sleep 6.09 h a night on average |
| Bellenger et al. 2022, *Sensors* 22:6723 | 10.3390/s22186723 * | HRV day-to-day variation, 3–13% of log-RMSSD |
| Nunan et al. 2010, *Pacing Clin Electrophysiol* | 10.1111/j.1540-8159.2010.02841.x * | Short-term RMSSD average ~42 ms, normal range 19–75 ms |
| Kikuya et al. 2008, *Hypertension* (Ohasama study) | 10.1161/HYPERTENSIONAHA.107.104620 * | Home systolic BP day-to-day spread ~9 mmHg; level 117.3, between-person SD 13.4 |
| Coskun et al. 2020, *Clin Chem Lab Med* 58:25 | 10.1515/cclm-2019-0658 | Lymphocytes: within-person 10.1%, between-person 23.9% |
| Bigley et al. 2019, *J Appl Physiol* | 10.1152/japplphysiol.00761.2018 * | NK cell activity −50% at flight day 90 |
| Mehta et al. 2017, *npj Microgravity* | 10.1038/s41526-017-0015-y | 61% of ISS crew shed herpesviruses |
| Agha et al. 2020, *J Appl Physiol* | 10.1152/japplphysiol.00560.2019 | Salivary sIgA rises in flight (signal not simulated) |
| Zhang et al. 2020, *Science Advances* 6:eaaz1334 | 10.1126/sciadv.aaz1334 | Moon surface dose: 13.2 µGy/h absorbed, 1,369 µSv/day dose equivalent |
| Zeitlin et al. 2013, *Science* 340:1080 | 10.1126/science.1235989 * | Mars transit dose equivalent 1.84 mSv/day |
| Hassler et al. 2014, *Science* 343 | 10.1126/science.1244797 | Mars cruise 0.48 and surface 0.21 mGy/day; surface 0.67 mSv/day |
| Berger et al. 2018, *Space Weather* (DOSIS 3D) | not found ([PDF](https://elib.dlr.de/120788/1/ME-SBA-2018-Berger-Matthi%C3%A4_et%20al-DOSIS-3D_Space%20Weather.pdf)) | Solar event of 10 Sep 2017 added 0.146 mGy on the ISS |
| NASA-STD-3001 | — | Radiation limits: 600 mSv career, 250 mSv per solar event |
| Hughson et al. 2012, *J Appl Physiol* | 10.1152/japplphysiol.01196.2011 * | ISS resting HR unchanged in flight with exercise; HRV high-frequency power falls |
| Exercise on the ISS, *npj Microgravity* 2023 | 10.1038/s41526-023-00256-5 | ISS crews log ~600 min of exercise a week (450–720) |
| Song et al. 2025, *IEEE TBME*; BIDSleep dataset (ODC-By) | — | Wearable heart rate and sleep; cite when used |

| Jones, Basner, Mollicone, Mott, Dinges 2022, *SLEEP* 45:zsac006 | 10.1093/sleep/zsac006 | ISS astronauts: sleep 6.5 h, efficiency 91.8%; stress ~38/100 in flight; stress +7.7 at ≤4 h sleep |
| Basner, Mollicone, Dinges 2011, *Acta Astronautica* 69:949 | 10.1016/j.actaastro.2011.07.015 | Rested 3-min PVT-B ≈ 7.5% lapses (≥355 ms); tracks the 10-min PVT |

| Mehta et al. 2017; NASA NTRS 20110000846 | 10.1038/s41526-017-0015-y | Shedding: 3% of samples in healthy controls; 23% of astronaut saliva samples EBV-positive |
| TINKL NK assay study (PubMed 23567516) | — | NK natural killing: 14% inter-test CV in 123 healthy adults |
| 5-min PVT test-retest study (J Neurosci Methods 2021); Hörmann et al. 2013 | — | PVT lapse repeat-test agreement ICC 0.59 (r 0.42–0.61) |
| ENERGY study, *npj Microgravity* 2024 | 10.1038/s41526-024-00360-0 | ISS aerobic exercise 168 ± 44 min/week (context for the exercise assumption) |

Still wanted: the Jones 2022 supplement (astronaut lapse levels, Fig S5A).
