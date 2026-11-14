#include "wokwi-api.h"
#include <stdlib.h>
#include <string.h>

#define FB_W 64
#define FB_H 32

#define HR_LO   30.0f
#define HR_HI   130.0f
#define HR_DEF  60.0f

#define HRV_LO  0.0f
#define HRV_HI  200.0f
#define HRV_DEF 55.0f

#define ON_DEF  1.0f

#define REFRESH_US 10000

typedef struct {
  pin_t pin_hr;
  pin_t pin_hrv;
  pin_t pin_on;
  uint32_t attr_hr;
  uint32_t attr_hrv;
  uint32_t attr_on;
  buffer_t fb;
  uint8_t pixels[FB_W * FB_H * 4];
} chip_state_t;

static void set_px(chip_state_t *c, int x, int y, uint8_t r, uint8_t g, uint8_t b) {
  if (x < 0 || x >= FB_W || y < 0 || y >= FB_H) return;
  int idx = (y * FB_W + x) * 4;
  c->pixels[idx + 0] = r;
  c->pixels[idx + 1] = g;
  c->pixels[idx + 2] = b;
  c->pixels[idx + 3] = 255;
}

static void draw_screen(chip_state_t *c, bool on) {
  static const uint8_t ecg[32] = {
    16,16,16,16,15,14,15,16,16,18,6,26,13,16,16,14,
    13,14,16,16,16,16,16,16,16,16,16,16,16,16,16,16
  };
  for (int y = 0; y < FB_H; y++) {
    for (int x = 0; x < FB_W; x++) {
      bool border = (x == 0 || x == FB_W - 1 || y == 0 || y == FB_H - 1);
      if (border) {
        set_px(c, x, y, on ? 220 : 80, on ? 50 : 80, on ? 60 : 80);
      } else {
        set_px(c, x, y, 14, 18, 28);
      }
    }
  }
  uint8_t r = on ? 60 : 90, g = on ? 235 : 90, b = on ? 120 : 90;
  for (int x = 2; x < FB_W - 2; x++) {
    int y0 = ecg[x % 32];
    int y1 = ecg[(x + 1) % 32];
    int lo = y0 < y1 ? y0 : y1;
    int hi = y0 > y1 ? y0 : y1;
    for (int y = lo; y <= hi; y++) {
      set_px(c, x, y, r, g, b);
    }
  }
  buffer_write(c->fb, 0, c->pixels, sizeof(c->pixels));
}

static float value_to_voltage(float val, float lo, float hi) {
  if (val < lo) val = lo;
  if (val > hi) val = hi;
  return 3.3f * (val - lo) / (hi - lo);
}

static void update_outputs(chip_state_t *chip) {
  float hr = attr_read_float(chip->attr_hr);
  float hrv = attr_read_float(chip->attr_hrv);
  float on = attr_read_float(chip->attr_on);

  pin_dac_write(chip->pin_hr, value_to_voltage(hr, HR_LO, HR_HI));
  pin_dac_write(chip->pin_hrv, value_to_voltage(hrv, HRV_LO, HRV_HI));
  pin_write(chip->pin_on, on >= 0.5f ? HIGH : LOW);
  draw_screen(chip, on >= 0.5f);
}

static void on_timer(void *user_data) {
  update_outputs((chip_state_t *)user_data);
}

void chip_init(void) {
  chip_state_t *chip = malloc(sizeof(chip_state_t));
  uint32_t w = FB_W, h = FB_H;
  chip->fb = framebuffer_init(&w, &h);

  pin_init("VCC", INPUT);
  pin_init("GND", INPUT);
  chip->pin_hr = pin_init("HR", ANALOG);
  chip->pin_hrv = pin_init("HRV", ANALOG);
  chip->pin_on = pin_init("ON", OUTPUT);

  chip->attr_hr = attr_init_float("hr", HR_DEF);
  chip->attr_hrv = attr_init_float("hrv", HRV_DEF);
  chip->attr_on = attr_init_float("on", ON_DEF);

  update_outputs(chip);

  const timer_config_t timer_cfg = {
    .callback = on_timer,
    .user_data = chip,
  };
  timer_t timer = timer_init(&timer_cfg);
  timer_start(timer, REFRESH_US, true);
}
