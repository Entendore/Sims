from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont

# ===================== CONSTANTS =====================
WIDTH, HEIGHT = 1280, 720
GW, GH = WIDTH, HEIGHT  # Full-screen game area — no panel

PHERO_RES = 4
PW = GW // PHERO_RES
PH = GH // PHERO_RES

ANT_COUNT = 80
SPOT_COUNT = 10
PREDATOR_COUNT = 3

ANT_SIZE = 4
SPOT_SIZE = 18
NEST_SIZE = 30
ANT_SPEED = 2
DETECT_RANGE = 80
COLLECT_RATE = 0.5
MAX_FOOD = 20
PHERO_EVAP = 0.995

SCOUT, WORKER, SOLDIER = 0, 1, 2
FOOD_P, DANGER_P = 0, 1

RECORD_FPS = 30

# Colors (QColor compatible tuples)
WHITE       = (255, 255, 255)
BLACK       = (0, 0, 0)
BROWN       = (139, 69, 19)
GREEN       = (34, 139, 34)
DARK_GREEN  = (0, 80, 0)
RED         = (255, 50, 50)
YELLOW      = (255, 255, 0)
BLUE        = (40, 100, 200)
WATER_BLUE  = (64, 164, 223)
GRAY        = (128, 128, 128)
PURPLE      = (160, 50, 200)
ORANGE      = (255, 165, 0)
DARK_RED    = (139, 0, 0)
CYAN        = (0, 200, 200)
DARK_GRAY   = (64, 64, 64)
LIGHT_GRAY  = (192, 192, 192)
NEST_INNER  = (210, 180, 140)
RAIN_CLR    = (100, 149, 237)

# Fonts
FONT_SM    = QFont("Consolas", 10)
FONT_MD    = QFont("Consolas", 13)
FONT_LG    = QFont("Consolas", 16, QFont.Bold)
FONT_TITLE = QFont("Consolas", 18, QFont.Bold)