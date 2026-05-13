import pygame
import random
from config import NEST_SIZE, BROWN, NEST_INNER, DARK_GRAY, BLACK, FONT_MD, SCOUT, WORKER, SOLDIER
from ant import Ant

class Colony:
    def __init__(self, nx, ny):
        self.nx, self.ny = nx, ny
        self.food_storage = 0.0
        self.total_collected = 0.0
        self.ants_lost = 0
        self.ants_born = 0
        self.spawn_cost = 10
        self.spawn_cd = 0
        self.spawn_interval = 120

    def deposit(self, amt):
        self.food_storage += amt
        self.total_collected += amt

    def can_spawn(self):
        return self.food_storage >= self.spawn_cost and self.spawn_cd <= 0

    def spawn(self):
        self.food_storage -= self.spawn_cost
        self.spawn_cd = self.spawn_interval
        self.ants_born += 1
        r = random.random()
        t = SCOUT if r < 0.25 else (WORKER if r < 0.7 else SOLDIER)
        return Ant(self.nx, self.ny, t)

    def update(self):
        if self.spawn_cd > 0: self.spawn_cd -= 1

    def draw(self, surf):
        pygame.draw.circle(surf, BROWN, (int(self.nx), int(self.ny)), NEST_SIZE)
        pygame.draw.circle(surf, NEST_INNER, (int(self.nx), int(self.ny)), NEST_SIZE - 5)
        pygame.draw.circle(surf, DARK_GRAY, (int(self.nx), int(self.ny)), NEST_SIZE, 2)
        t = FONT_MD.render(f"{self.food_storage:.0f}", True, BLACK)
        surf.blit(t, (self.nx - t.get_width() // 2, self.ny - t.get_height() // 2))