import pandas as pd

from data.process import clean_co2, daily_dose, timepoint_day


def test_daily_dose_is_time_weighted():
    # 12 h at 10 uGy/h sampled every 90 s, then 12 h at 30 uGy/h sampled every 20 s:
    # true dose = 120 + 360 = 480 uGy; a plain mean of samples would give ~26 uGy/h -> ~630.
    t0 = pd.Timestamp("2022-01-01")
    slow = [(t0 + pd.Timedelta(seconds=s), 10.0) for s in range(0, 12 * 3600, 90)]
    fast = [(t0 + pd.Timedelta(seconds=12 * 3600 + s), 30.0) for s in range(0, 12 * 3600 + 20, 20)]
    df = pd.DataFrame(slow + fast, columns=["timestamp", "absorbed_dose_rate"]).assign(instrument_id="D1")
    day = daily_dose(df)
    assert abs(day["absorbed_ugy_per_day"].iloc[0] - 480) < 5


def test_clean_co2_drops_fill_and_impossible_values():
    real = pd.Series([2600.0 + i for i in range(20)])
    flat = pd.Series([2000.0] * 12)
    v = clean_co2(pd.concat([real, flat, pd.Series([300.0, 2700.0])], ignore_index=True))
    assert v.iloc[:20].notna().all()      # varying real readings kept
    assert v.iloc[20:32].isna().all()     # 1 h of identical values = gap fill
    assert pd.isna(v.iloc[32])            # 300 ppm is below outdoor air
    assert v.iloc[33] == 2700.0


def test_timepoint_day():
    assert timepoint_day("L-92") == -92
    assert timepoint_day("R+1") == 4
