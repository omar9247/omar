#include <Arduino.h>
#include <math.h>
#include <stdio.h>
#include <time.h>

#define CREW_ID "cm2"

#ifndef SECONDS_PER_DAY
#define SECONDS_PER_DAY 10
#endif

#define LAB_INTERVAL_DAYS 7
#define START_EPOCH       1794650400LL  // 2026-11-14T10:00:00Z
#define DAY_SECONDS       86400LL

// Wokwi virtual ADCs use a fixed 5.0 V reference (docs.wokwi.com/chips-api/analog),
// while the custom chips output 0..3.3 V per docs/wokwi-requirements.md.
// Change ADC_VREF to 3.3f if flashing to physical ESP32 hardware.
#define ADC_VREF  5.0f
#define CHIP_VMAX 3.3f

#define PIN_PULSE_ON 25
#define PIN_VIRAL    26

struct AnalogSignal {
  const char *name;
  uint8_t pin;
  float lo;
  float hi;
  int decimals;
  bool requires_pulse;
  bool is_lab;
};

static const AnalogSignal ANALOG_SIGNALS[] = {
  {"resting_hr_bpm",     34, 30.0f,   130.0f, 1, true,  false},
  {"rmssd_ms",           35,  0.0f,   200.0f, 1, true,  false},
  {"cabin_co2_mmhg",     32,  0.0f,    10.0f, 2, false, false},
  {"lymphocytes_per_ul", 33,  0.0f,  6000.0f, 0, false, true},
  {"il6_pg_ml",          36,  0.0f,    25.0f, 1, false, true},
  {"nk_activity_pct",    39,  0.0f,   150.0f, 1, false, true},
};

static uint32_t sim_day = 0;
static unsigned long next_day_ms = 0;

static void format_ts(uint32_t day, char *buf, size_t len) {
  time_t t = (time_t)(START_EPOCH + (int64_t)day * DAY_SECONDS);
  struct tm utc;
  gmtime_r(&t, &utc);
  strftime(buf, len, "%Y-%m-%dT%H:%M:%SZ", &utc);
}

static void print_reading(const char *ts, const char *signal, float value, int decimals) {
  char line[256];
  snprintf(
      line,
      sizeof(line),
      "{\"crew_id\":\"%s\",\"ts\":\"%s\",\"signal\":\"%s\",\"value\":%.*f,\"source\":\"wokwi\",\"provenance\":\"simulated\"}",
      CREW_ID,
      ts,
      signal,
      decimals,
      value);
  Serial.println(line);
}

static float read_scaled(const AnalogSignal &sig) {
  int raw = analogRead(sig.pin);
  float voltage = ADC_VREF * (raw / 4095.0f);
  float val = sig.lo + (sig.hi - sig.lo) * (voltage / CHIP_VMAX);
  if (val < sig.lo) val = sig.lo;
  if (val > sig.hi) val = sig.hi;
  if (sig.decimals == 0) {
    val = roundf(val);
  }
  return val;
}

void setup() {
  Serial.begin(115200);
  analogReadResolution(12);
  pinMode(PIN_PULSE_ON, INPUT);
  pinMode(PIN_VIRAL, INPUT);
  next_day_ms = millis();
}

void loop() {
  unsigned long now = millis();
  if ((long)(now - next_day_ms) < 0) {
    delay(10);
    return;
  }

  char ts[32];
  format_ts(sim_day, ts, sizeof(ts));
  bool pulse_on = (digitalRead(PIN_PULSE_ON) == HIGH);
  bool lab_day = (sim_day % LAB_INTERVAL_DAYS == 0);

  Serial.print("# day ");
  Serial.println(sim_day);

  for (size_t i = 0; i < sizeof(ANALOG_SIGNALS) / sizeof(ANALOG_SIGNALS[0]); i++) {
    const AnalogSignal &sig = ANALOG_SIGNALS[i];
    if (sig.requires_pulse && !pulse_on) {
      continue;
    }
    if (sig.is_lab && !lab_day) {
      continue;
    }
    print_reading(ts, sig.name, read_scaled(sig), sig.decimals);
  }

  if (lab_day) {
    int viral = (digitalRead(PIN_VIRAL) == HIGH) ? 1 : 0;
    print_reading(ts, "viral_pcr_positive", (float)viral, 0);
  }

  sim_day++;
  next_day_ms += (unsigned long)SECONDS_PER_DAY * 1000UL;
}
