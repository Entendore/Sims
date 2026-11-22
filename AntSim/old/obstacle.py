import random
import math
import pygame
from config import GW, GH, BLACK, DARK_GRAY
from utils import dist

class Obstacle:
    def __init__(self, circular=False, x=None, y=None):
        self.circular = circular
        self.color = (random.randint(100, 140),) * 3
        if circular:
            self.radius = random.randint(25, 55)
            self.x = x if x else random.randint(self.radius + 10, GW - self.radius - 10)
            self.y = y if y else random.randint(self.radius + 10, GH - self.radius - 10)
            self.width = self.radius * 2
            self.height = self.radius * 2
        else:
            self.width = random.randint(40, 120)
            self.height = random.randint(40, 120)
            self.x = x if x else random.randint(self.width // 2 + 10, GW - self.width // 2 - 10)
            self.y = y if y else random.randint(self.height // 2 + 10, GH - self.height // 2 - 10)
            self.radius = 0
            self.points = [
                (self.x - self.width // 2, self.y - self.height // 2),
                (self.x + self.width // 2, self.y - self.height // 2),
                (self.x + self.width // 2, self.y + self.height // 2),
                (self.x - self.width // 2, self.y + self.height // 2),
            ]

    def collides_with(self, x, y, buf=5):
        if self.circular:
            return dist(self.x, self.y, x, y) < self.radius + buf
        return (self.x - self.width / 2 - buf <= x <= self.x + self.width / 2 + buf and
                self.y - self.height / 2 - buf <= y <= self.y + self.height / 2 + buf)

    def distance_to(self, x, y):
        if self.circular:
            return max(0, dist(self.x, self.y, x, y) - self.radius)
        dx = max(self.x - self.width / 2 - x, 0, x - (self.x + self.width / 2))
        dy = max(self.y - self.height / 2 - y, 0, y - (self.y + self.height / 2))
        return math.sqrt(dx * dx + dy * dy)

    def draw(self, surf):
        if self.circular:
            pygame.draw.circle(surf, self.color, (int(self.x), int(self.y)), self.radius)
            pygame.draw.circle(surf, BLACK, (int(self.x), int(self.y)), self.radius, 2)
            for a in range(0, 360, 45):
                ex = self.x + math.cos(math.radians(a)) * self.radius * 0.7
                ey = self.y + math.sin(math.radians(a)) * self.radius * 0.7
                pygame.draw.line(surf, DARK_GRAY, (int(self.x), int(self.y)), (int(ex), int(ey)), 1)
        else:
            pygame.draw.polygon(surf, self.color, self.points)
            pygame.draw.polygon(surf, BLACK, self.points, 2)
            for row in range(int(self.y - self.height / 2) + 8, int(self.y + self.height / 2), 12):
                pygame.draw.line(surf, DARK_GRAY,
                                 (int(self.x - self.width / 2), row),
                                 (int(self.x + self.width / 2), row), 1)