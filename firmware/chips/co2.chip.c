#include "wokwi-api.h"
#include <stdlib.h>

#define FB_W 64
#define FB_H 32

#define CO2_LO  0.0f
#define CO2_HI  10.0f
#define CO2_DEF 2.2f

#define REFRESH_US 10000

typedef struct {
  pin_t pin_co2;
  uint32_t attr_co2;
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

static void draw_screen(chip_state_t *c, float co2) {
  float frac = (co2 - CO2_LO) / (CO2_HI - CO2_LO);
  if (frac < 0.0f) frac = 0.0f;
  if (frac > 1.0f) frac = 1.0f;
  int fill_w = (int)(frac * (FB_W - 12));
  uint8_t br = co2 > 3.0f ? 235 : (co2 >= 2.5f ? 245 : 70);
  uint8_t bg = co2 > 3.0f ? 60  : (co2 >= 2.5f ? 190 : 210);
  uint8_t bb = co2 > 3.0f ? 60  : (co2 >= 2.5f ? 40  : 140);

  for (int y = 0; y < FB_H; y++) {
    for (int x = 0; x < FB_W; x++) {
      if (x == 0 || x == FB_W - 1 || y == 0 || y == FB_H - 1) {
        set_px(c, x, y, 230, 180, 50);
      } else if (x >= 6 && x < 6 + fill_w && y >= 11 && y <= 20) {
        set_px(c, x, y, br, bg, bb);
      } else if (x >= 5 && x <= FB_W - 6 && y >= 10 && y <= 21) {
        set_px(c, x, y, 36, 42, 56);
      } else {
        set_px(c, x, y, 14, 18, 28);
      }
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
  float co2 = attr_read_float(chip->attr_co2);
  pin_dac_write(chip->pin_co2, value_to_voltage(co2, CO2_LO, CO2_HI));
  draw_screen(chip, co2);
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
  chip->pin_co2 = pin_init("CO2", ANALOG);

  chip->attr_co2 = attr_init_float("co2", CO2_DEF);

  update_outputs(chip);

  const timer_config_t timer_cfg = {
    .callback = on_timer,
    .user_data = chip,
  };
  timer_t timer = timer_init(&timer_cfg);
  timer_start(timer, REFRESH_US, true);
}
