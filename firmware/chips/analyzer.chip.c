#include "wokwi-api.h"
#include <stdlib.h>

#define FB_W 64
#define FB_H 32

#define LYM_LO  0.0f
#define LYM_HI  6000.0f
#define LYM_DEF 2679.0f

#define IL6_LO  0.0f
#define IL6_HI  25.0f
#define IL6_DEF 3.7f

#define NK_LO   0.0f
#define NK_HI   150.0f
#define NK_DEF  100.0f

#define VIR_DEF 0.0f

#define REFRESH_US 10000

typedef struct {
  pin_t pin_lym;
  pin_t pin_il6;
  pin_t pin_nk;
  pin_t pin_vir;
  uint32_t attr_lym;
  uint32_t attr_il6;
  uint32_t attr_nk;
  uint32_t attr_vir;
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

static int bar_h(float val, float lo, float hi) {
  float f = (val - lo) / (hi - lo);
  if (f < 0.0f) f = 0.0f;
  if (f > 1.0f) f = 1.0f;
  return (int)(f * 22.0f);
}

static void draw_screen(chip_state_t *c, float lym, float il6, float nk, bool vir) {
  int h_lym = bar_h(lym, LYM_LO, LYM_HI);
  int h_il6 = bar_h(il6, IL6_LO, IL6_HI);
  int h_nk  = bar_h(nk,  NK_LO,  NK_HI);

  for (int y = 0; y < FB_H; y++) {
    for (int x = 0; x < FB_W; x++) {
      if (x == 0 || x == FB_W - 1 || y == 0 || y == FB_H - 1) {
        set_px(c, x, y, 70, 200, 235);
      } else if (x >= 8 && x <= 16 && y >= 27 - h_lym && y <= 26) {
        set_px(c, x, y, 160, 110, 255);
      } else if (x >= 22 && x <= 30 && y >= 27 - h_il6 && y <= 26) {
        set_px(c, x, y, 60, 220, 240);
      } else if (x >= 36 && x <= 44 && y >= 27 - h_nk && y <= 26) {
        set_px(c, x, y, 235, 90, 210);
      } else if (x >= 51 && x <= 57 && y >= 6 && y <= 12) {
        set_px(c, x, y, vir ? 245 : 60, vir ? 60 : 210, vir ? 60 : 120);
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
  float lym = attr_read_float(chip->attr_lym);
  float il6 = attr_read_float(chip->attr_il6);
  float nk  = attr_read_float(chip->attr_nk);
  float vir = attr_read_float(chip->attr_vir);

  pin_dac_write(chip->pin_lym, value_to_voltage(lym, LYM_LO, LYM_HI));
  pin_dac_write(chip->pin_il6, value_to_voltage(il6, IL6_LO, IL6_HI));
  pin_dac_write(chip->pin_nk,  value_to_voltage(nk,  NK_LO,  NK_HI));
  pin_write(chip->pin_vir, vir >= 0.5f ? HIGH : LOW);
  draw_screen(chip, lym, il6, nk, vir >= 0.5f);
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
  chip->pin_lym = pin_init("LYM", ANALOG);
  chip->pin_il6 = pin_init("IL6", ANALOG);
  chip->pin_nk  = pin_init("NK", ANALOG);
  chip->pin_vir = pin_init("VIR", OUTPUT);

  chip->attr_lym = attr_init_float("lym", LYM_DEF);
  chip->attr_il6 = attr_init_float("il6", IL6_DEF);
  chip->attr_nk  = attr_init_float("nk",  NK_DEF);
  chip->attr_vir = attr_init_float("vir", VIR_DEF);

  update_outputs(chip);

  const timer_config_t timer_cfg = {
    .callback = on_timer,
    .user_data = chip,
  };
  timer_t timer = timer_init(&timer_cfg);
  timer_start(timer, REFRESH_US, true);
}
