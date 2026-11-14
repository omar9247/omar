"""Validate Wokwi Serial JSON lines against contract/schema.py Reading."""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from contract.schema import Reading  # noqa: E402

START_TS = datetime(2026, 11, 14, 10, 0, 0, tzinfo=timezone.utc)
LAB_INTERVAL_DAYS = 7

DEFAULTS = {
    "resting_hr_bpm": 60.0,
    "rmssd_ms": 55.0,
    "cabin_co2_mmhg": 2.2,
    "lymphocytes_per_ul": 2679.0,
    "il6_pg_ml": 3.7,
    "nk_activity_pct": 100.0,
    "viral_pcr_positive": 0.0,
}

PULSE_SIGNALS = {"resting_hr_bpm", "rmssd_ms"}
CABIN_SIGNALS = {"cabin_co2_mmhg"}
LAB_SIGNALS = {
    "lymphocytes_per_ul",
    "il6_pg_ml",
    "nk_activity_pct",
    "viral_pcr_positive",
}
ALLOWED_SIGNALS = set(DEFAULTS.keys())
BOOT_PREFIXES = (
    "ets ",
    "rst:",
    "configsip:",
    "clk_drv:",
    "mode:",
    "load:",
    "ho ",
    "entry ",
)


def validate_lines(
    lines: list[str],
    expect_defaults: bool = False,
    timeline: bool = False,
    crew: str = "cm2",
) -> tuple[int, list[str], dict[str, int], str | None]:
    passed = 0
    errors: list[str] = []
    note: str | None = None
    seen_json = False

    non_empty_indices = [
        idx
        for idx, raw in enumerate(lines)
        if raw.strip() and not raw.strip().startswith("#")
    ]
    last_non_empty_idx = non_empty_indices[-1] if non_empty_indices else -1

    days_seen: list[datetime] = []
    signals_by_day: dict[datetime, set[str]] = defaultdict(set)

    for idx, raw in enumerate(lines):
        lineno = idx + 1
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if not seen_json and line.startswith(BOOT_PREFIXES):
            continue
        seen_json = True

        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            if idx == last_non_empty_idx:
                note = f"Ignored truncated final line {lineno}: {line[:80]}"
                continue
            errors.append(f"Line {lineno}: JSON error: {exc} | {line}")
            continue

        try:
            reading = Reading(**payload)
        except Exception as exc:
            errors.append(f"Line {lineno}: schema error: {exc} | {line}")
            continue

        if reading.signal not in ALLOWED_SIGNALS:
            errors.append(f"Line {lineno}: unexpected signal {reading.signal!r}")
            continue
        if reading.source != "wokwi":
            errors.append(f"Line {lineno}: expected source='wokwi', got {reading.source!r}")
            continue
        if reading.provenance != "simulated":
            errors.append(
                f"Line {lineno}: expected provenance='simulated', got {reading.provenance!r}"
            )
            continue

        if expect_defaults:
            target = DEFAULTS[reading.signal]
            rel_tol = 0.0 if target == 0.0 else 0.015 * abs(target)
            if target == 0.0:
                if reading.value != 0.0:
                    errors.append(
                        f"Line {lineno}: {reading.signal}={reading.value}, expected 0"
                    )
                    continue
            elif abs(reading.value - target) > rel_tol:
                errors.append(
                    f"Line {lineno}: {reading.signal}={reading.value}, expected ~{target} (±1.5%)"
                )
                continue

        if timeline:
            raw_ts = payload.get("ts", "")
            if not isinstance(raw_ts, str) or not raw_ts.endswith("Z"):
                errors.append(f"Line {lineno}: ts missing 'Z' suffix: {raw_ts!r}")
                continue
            if reading.crew_id != crew:
                errors.append(
                    f"Line {lineno}: expected crew_id={crew!r}, got {reading.crew_id!r}"
                )
                continue
            ts_utc = reading.ts.astimezone(timezone.utc)
            if ts_utc not in signals_by_day:
                days_seen.append(ts_utc)
            if reading.signal in signals_by_day[ts_utc]:
                errors.append(
                    f"Line {lineno}: duplicate signal {reading.signal!r} for {raw_ts}"
                )
                continue
            signals_by_day[ts_utc].add(reading.signal)

        passed += 1

    stats = {"days": 0, "lab_days": 0, "pulse_off_days": 0}
    if timeline:
        if not days_seen:
            errors.append("Timeline: no readings found")
        else:
            # Drop a trailing partial day caused by timeout mid-cycle only if it's the last day
            # AND a truncated final line was seen.
            full_days = days_seen
            for n, ts_utc in enumerate(full_days):
                expected_ts = START_TS + timedelta(days=n)
                if ts_utc != expected_ts:
                    errors.append(
                        f"Day {n}: expected ts={expected_ts.strftime('%Y-%m-%dT%H:%M:%SZ')}, "
                        f"got {ts_utc.strftime('%Y-%m-%dT%H:%M:%SZ')}"
                    )
                sigs = signals_by_day[ts_utc]
                is_partial_tail = (note is not None) and (n == len(full_days) - 1)
                if is_partial_tail:
                    continue
                if not CABIN_SIGNALS.issubset(sigs):
                    errors.append(f"Day {n} ({ts_utc.date()}): missing cabin_co2_mmhg")
                pulse_count = len(sigs & PULSE_SIGNALS)
                if pulse_count not in (0, 2):
                    errors.append(
                        f"Day {n} ({ts_utc.date()}): partial pulse signals {sorted(sigs & PULSE_SIGNALS)}"
                    )
                elif pulse_count == 0:
                    stats["pulse_off_days"] += 1

                labs_present = sigs & LAB_SIGNALS
                if n % LAB_INTERVAL_DAYS == 0:
                    if labs_present != LAB_SIGNALS:
                        errors.append(
                            f"Day {n} ({ts_utc.date()}): expected all 4 lab signals, got {sorted(labs_present)}"
                        )
                    else:
                        stats["lab_days"] += 1
                else:
                    if labs_present:
                        errors.append(
                            f"Day {n} ({ts_utc.date()}): unexpected lab signals on non-lab day: {sorted(labs_present)}"
                        )
            stats["days"] = len(full_days) - (1 if note is not None and len(full_days) > 0 else 0)

    return passed, errors, stats, note


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Wokwi Serial output.")
    parser.add_argument(
        "file",
        nargs="?",
        help="Path to captured Serial text file (reads stdin if omitted).",
    )
    parser.add_argument(
        "--expect-defaults",
        action="store_true",
        help="Also verify values match defaults within ~1%%.",
    )
    parser.add_argument(
        "--timeline",
        action="store_true",
        help="Verify phase 2 daily timeline, 'Z' suffix, crew_id, and 7-day lab cadence.",
    )
    parser.add_argument(
        "--crew",
        default="cm2",
        help="Expected crew_id when --timeline is enabled (default: cm2).",
    )
    args = parser.parse_args()

    if args.file:
        text = Path(args.file).read_text(encoding="utf-8", errors="replace")
    else:
        text = sys.stdin.read()

    passed, errors, stats, note = validate_lines(
        text.splitlines(),
        expect_defaults=args.expect_defaults,
        timeline=args.timeline,
        crew=args.crew,
    )
    if note:
        print(f"Note: {note}")
    if args.timeline:
        print(
            f"Passed: {passed}, Failed: {len(errors)} | "
            f"Days: {stats['days']}, Lab days: {stats['lab_days']}, "
            f"Pulse-off days: {stats['pulse_off_days']}"
        )
    else:
        print(f"Passed: {passed}, Failed: {len(errors)}")
    for err in errors:
        print(f"  ERROR: {err}", file=sys.stderr)
    return 1 if errors or passed == 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
