"""Download the open datasets into data/raw/<source>/ and record each file in data/raw/MANIFEST.json.

    uv run python data/fetch.py            # everything
    uv run python data/fetch.py radlab     # one source

Re-running skips files already present (and hash-checked where the source publishes hashes).
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

RAW = Path(__file__).parent / "raw"
MANIFEST = RAW / "MANIFEST.json"
UA = {"User-Agent": "aura-bio-data-fetch/0.1"}


def get(url: str, timeout: int = 60, tries: int = 4) -> bytes:
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return r.read()
        except OSError:
            if attempt == tries - 1:
                raise
            time.sleep(5 * 2 ** attempt)  # 5, 10, 20 s: rides out short DNS/network drops


def save(dest: Path, url: str, sha256: str | None = None) -> dict:
    if dest.exists() and (sha256 is None or hashlib.sha256(dest.read_bytes()).hexdigest() == sha256):
        data = dest.read_bytes()
    else:
        data = get(url)
        got = hashlib.sha256(data).hexdigest()
        if sha256 and got != sha256:
            raise ValueError(f"hash mismatch for {url}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    return {"path": str(dest.relative_to(RAW)), "url": url, "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


# --- 4. PhysioNet BIDSleep: heart rate + EEG sleep-stage labels, no accelerometry -------------
BIDS = "https://physionet.org/files/bidsleep-dataset/1.0.1/"


def bidsleep() -> list[dict]:
    sums = get(BIDS + "SHA256SUMS.txt").decode().split("\n")
    wanted = [(h, p) for h, p in (l.split(maxsplit=1) for l in sums if l.strip())
              if not p.endswith("motion.csv")]
    out = RAW / "bidsleep"

    def one(hp):  # one failed file must not discard the rest; a re-run picks it up
        try:
            return save(out / hp[1], BIDS + hp[1], hp[0])
        except Exception as e:
            print(f"  {hp[1]}: skipped ({e})")

    with ThreadPoolExecutor(4) as ex:
        recs = [r for r in ex.map(one, wanted) if r]
    print(f"  {len(recs)}/{len(wanted)} files")
    return recs


# --- 2. RadLab: ISS DosTel absorbed dose rate (uGy/hour); aggregate to daily later -----------
RADLAB = "https://visualization.osdr.nasa.gov/radlab/api/"
# DosTel coverage ends mid-April 2022; Jan-Mar 2022 has both detectors every day.
RADLAB_START, RADLAB_DAYS = date(2022, 1, 1), 90


def radlab() -> list[dict]:
    recs = []
    for i in range(0, RADLAB_DAYS, 10):  # 10-day chunks keep each request small
        a, b = RADLAB_START + timedelta(i), RADLAB_START + timedelta(min(i + 10, RADLAB_DAYS))
        url = (f"{RADLAB}?spacecraft=ISS&instrument=DosTel&timestamp%3E={a}T00%3A00"
               f"&timestamp%3C{b}T00%3A00&absorbed_dose_rate&dose_equivalent_rate&format=csv")
        recs.append(save(RAW / "radlab" / f"dostel_{a}_{b}.csv", url))
    return recs


# --- 5. OSDR Inspiration4 clinical tables (CBC, CMP, serum immune/cardio panels) -------------
OSDR_FILES = {
    569: ["LSDS-7_Complete_Blood_Count_CBC_TRANSFORMED.csv",
          "LSDS-7_Complete_Blood_Count_CBC.upload_SUBMITTED.csv"],
    575: ["LSDS-8_Comprehensive_Metabolic_Panel_CMP_TRANSFORMED.csv",
          "LSDS-8_Multiplex_serum_immune_EvePanel_TRANSFORMED.csv",
          "LSDS-8_Multiplex_serum_cardiovascular_EvePanel_TRANSFORMED.csv",
          "LSDS-8_Multiplex_serum.immune.AlamarPanel_TRANSFORMED.csv",
          "OSD-575_metadata_OSD-575-ISA.zip"],
}


def inspiration4() -> list[dict]:
    recs = []
    for osd, names in OSDR_FILES.items():
        listing = json.loads(get(f"https://osdr.nasa.gov/osdr/data/osd/files/{osd}"))
        files = {f["file_name"]: f for s in listing["studies"].values() for f in s["study_files"]}
        for n in names:
            url = "https://osdr.nasa.gov" + files[n]["remote_url"]
            recs.append(save(RAW / "inspiration4" / f"OSD-{osd}" / n, url))
    return recs


# --- 6. NOAA SWPC GOES integral proton flux (rolling 7 days) --------------------------------
def swpc() -> list[dict]:
    url = "https://services.swpc.noaa.gov/json/goes/primary/integral-protons-7-day.json"
    today = datetime.now(timezone.utc).date()
    return [save(RAW / "swpc" / f"integral-protons-7-day_{today}.json", url)]


# --- 1. OSDR Environmental Data App: ISS CO2 during Rodent Research missions ------------------
# API docs: https://visualization.osdr.nasa.gov/eda/api_reference . Values are ppm
# (median ~3600 ppm ~ 2.8 mmHg; 1 mmHg ~ 1316 ppm at 1 atm). 5-min cadence.
EDA = "https://visualization.osdr.nasa.gov/eda/api/missions/"


def eda() -> list[dict]:
    missions = [m["name"] for m in json.loads(get(EDA))]
    recs = []
    for m in missions:
        try:
            recs.append(save(RAW / "eda" / f"{m}_co2_iss.json", f"{EDA}{m}/co2/iss/"))
        except Exception as e:  # some missions have no CO2 series
            print(f"  {m}: skipped ({e})")
    return recs


SOURCES = {"eda": eda, "bidsleep": bidsleep, "radlab": radlab, "inspiration4": inspiration4,
           "swpc": swpc}


def main() -> None:
    names = sys.argv[1:] or list(SOURCES)
    for n in names:
        print(f"{n} ...", flush=True)
        try:
            recs = SOURCES[n]()
        except Exception as e:  # keep going with the other sources
            print(f"  FAILED: {e}")
            continue
        # re-read right before writing so parallel runs for other sources aren't clobbered
        manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
        manifest[n] = {"fetched": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                       "files": recs}
        RAW.mkdir(parents=True, exist_ok=True)
        MANIFEST.write_text(json.dumps(manifest, indent=1))
        print(f"  {len(recs)} files, {sum(r['bytes'] for r in recs) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
