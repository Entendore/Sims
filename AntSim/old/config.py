import pygame

# Pre-initialize mixer for custom generated sounds (44100Hz, 16-bit signed, Stereo, 512 buffer)
pygame.mixer.pre_init(44100, -16, 2, 512)
pygame.init()

# ===================== CONSTANTS =====================
WIDTH, HEIGHT = 1200, 750
PANEL_W = 280
GW = WIDTH - PANEL_W   # Game area width
GH = HEIGHT             # Game area height

PHERO_RES = 4           # Pheromone grid resolution (lower = faster)
PW = GW // PHERO_RES    # Pheromone grid width
PH = GH // PHERO_RES    # Pheromone grid height

ANT_COUNT = 60
SPOT_COUNT = 6
OBSTACLE_COUNT = 8
PREDATOR_COUNT = 2

ANT_SIZE = 5
SPOT_SIZE = 20
NEST_SIZE = 35
ANT_SPEED = 2
DETECT_RANGE = 80
COLLECT_RATE = 0.5
MAX_FOOD = 15
PHERO_EVAP = 0.995

SCOUT, WORKER, SOLDIER = 0, 1, 2
FOOD_P, DANGER_P = 0, 1

# Colors
WHITE      = (255, 255, 255)
BLACK      = (0, 0, 0)
BROWN      = (139, 69, 19)
GREEN      = (34, 139, 34)
RED        = (255, 0, 0)
YELLOW     = (255, 255, 0)
BLUE       = (0, 0, 255)
GRAY       = (128, 128, 128)
PURPLE     = (128, 0, 128)
ORANGE     = (255, 165, 0)
DARK_RED   = (139, 0, 0)
CYAN       = (0, 200, 200)
DARK_GRAY  = (64, 64, 64)
LIGHT_GRAY = (192, 192, 192)
NEST_INNER = (210, 180, 140)
PANEL_BG   = (30, 30, 40)
PANEL_TEXT  = (200, 200, 210)
PANEL_ACC  = (70, 170, 70)
RAIN_CLR   = (100, 149, 237)

# Fonts
FONT_SM    = pygame.font.SysFont("consolas", 14)
FONT_MD    = pygame.font.SysFont("consolas", 18)
FONT_LG    = pygame.font.SysFont("consolas", 24)
FONT_TITLE = pygame.font.SysFont("consolas", 28, bold=True)

# Surfaces
screen       = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Advanced Ant Colony Simulation — MDP & MCTS")
clock        = pygame.time.Clock()
game_surf    = pygame.Surface((GW, GH))
panel_surf   = pygame.Surface((PANEL_W, HEIGHT))
night_surf   = pygame.Surface((GW, GH), pygame.SRCALPHA)