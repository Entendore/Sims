import random
import math
from config import SPOT_SIZE, MAX_FOOD, GW, GH, FONT_SM, BLACK, DARK_RED
import pygame

class FeedingSpot:
    def __init__(self, x=None, y=None):
        self.x = x if x else random.randint(SPOT_SIZE + 10, GW - SPOT_SIZE - 10)
        self.y = y if y else random.randint(SPOT_SIZE + 10, GH - SPOT_SIZE - 10)
        self.food_amount = MAX_FOOD
        self.initial_food = MAX_FOOD
        self.regen_rate = 0.01

    def update(self, day_f):
        if self.food_amount < self.initial_food:
            self.food_amount = min(self.initial_food, self.food_amount + self.regen_rate * day_f)

    def valid(self, obs):
        return not any(o.collides_with(self.x, self.y, SPOT_SIZE) for o in obs)

    def draw(self, surf):
        r = self.food_amount / self.initial_food
        if r > 0.5: cr, cg = int(255 * (1 - (r - 0.5) * 2)), 255
        else: cr, cg = 255, int(255 * r * 2)
        pygame.draw.circle(surf, (cr, cg, 0), (int(self.x), int(self.y)), SPOT_SIZE)
        pygame.draw.circle(surf, BLACK, (int(self.x), int(self.y)), SPOT_SIZE, 1)
        for a in range(0, 360, 60):
            lx = self.x + math.cos(math.radians(a)) * SPOT_SIZE * 0.5
            ly = self.y + math.sin(math.radians(a)) * SPOT_SIZE * 0.5
            pygame.draw.circle(surf, DARK_RED, (int(lx), int(ly)), 2)
        t = FONT_SM.render(f"{self.food_amount:.1f}", True, BLACK)
        surf.blit(t, (self.x - t.get_width() // 2, self.y - t.get_height() // 2))