"""Global configuration for the Lunar Arcade Hub."""

import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
SOUND_DIR = os.path.join(ASSETS_DIR, "sounds")
IMAGE_DIR = os.path.join(ASSETS_DIR, "images")
FONT_DIR = os.path.join(ASSETS_DIR, "fonts")
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "lunar_arcade.db")

WIDTH, HEIGHT = 1200, 800
FPS = 60
APP_TITLE = "Lunar Arcade Hub"
VERSION = "2.3.0"
IS_WEB = sys.platform == "emscripten"

# ---------------------------------------------------------------- palette
BG_TOP = (7, 9, 26)
BG_BOTTOM = (15, 19, 46)
PANEL = (18, 23, 52)
PANEL_LIGHT = (27, 33, 70)
PANEL_DARK = (12, 15, 36)
BORDER = (52, 64, 120)
BORDER_SOFT = (38, 46, 88)

PURPLE = (155, 91, 255)
PURPLE_DEEP = (104, 62, 196)
CYAN = (55, 225, 255)
CYAN_DEEP = (26, 150, 190)
WHITE = (240, 244, 255)
MUTED = (142, 154, 192)
DIM = (96, 107, 145)
GREEN = (75, 245, 170)
GREEN_DEEP = (30, 150, 105)
GOLD = (255, 205, 75)
ORANGE = (255, 150, 70)
RED = (255, 95, 120)
BLUE = (90, 140, 255)
BLACK = (0, 0, 0)

DIFFICULTY_COLORS = [GREEN, CYAN, GOLD, ORANGE, RED]
