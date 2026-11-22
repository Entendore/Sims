import pygame
import random
import math

# ------------------ Configuration ------------------
WIDTH, HEIGHT = 800, 600
FPS = 60
NUM_PARTICLES = 30

# ------------------ Particle Class ------------------
class Particle:
    def __init__(self, x, y, color=(255, 255, 255), radius=5, rules=None):
        self.x = x
        self.y = y
        self.vx = random.uniform(-2, 2)
        self.vy = random.uniform(-2, 2)
        self.radius = radius
        self.color = color
        self.rules = rules if rules else []

    def update(self, particles):
        # Each particle applies its rules independently
        for rule in self.rules:
            rule(self, particles)

        # Update position based on velocity
        self.x += self.vx
        self.y += self.vy

        # Bounce off walls
        if self.x < 0 or self.x > WIDTH:
            self.vx *= -1
        if self.y < 0 or self.y > HEIGHT:
            self.vy *= -1

    def draw(self, screen):
        pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), self.radius)

# ------------------ Example Rules ------------------
def avoid_others(particle, particles, min_distance=30, strength=0.5):
    """Repel particle from others"""
    for other in particles:
        if other is particle:
            continue
        dx = particle.x - other.x
        dy = particle.y - other.y
        dist = math.hypot(dx, dy)
        if dist < min_distance and dist > 0:
            particle.vx += (dx/dist) * strength
            particle.vy += (dy/dist) * strength

def move_to_center(particle, particles, strength=0.2):
    """Move particle toward screen center"""
    center_x, center_y = WIDTH/2, HEIGHT/2
    dx = center_x - particle.x
    dy = center_y - particle.y
    particle.vx += dx * strength / 100
    particle.vy += dy * strength / 100

def random_motion(particle, particles, amount=0.3):
    """Randomly wiggle particle"""
    particle.vx += random.uniform(-amount, amount)
    particle.vy += random.uniform(-amount, amount)

# ------------------ Particle Types ------------------
PARTICLE_TYPES = {
    "A": {"color": (255, 100, 100), "radius": 5, "rules": [random_motion]},
    "B": {"color": (100, 255, 100), "radius": 6, "rules": [move_to_center, random_motion]},
    "C": {"color": (100, 100, 255), "radius": 7, "rules": [avoid_others, random_motion]},
}

# ------------------ Pygame Initialization ------------------
pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Rules-Driven Particle Simulation")
clock = pygame.time.Clock()

# ------------------ Create Particles ------------------
particles = []
for _ in range(NUM_PARTICLES):
    type_name = random.choice(list(PARTICLE_TYPES.keys()))
    type_info = PARTICLE_TYPES[type_name]
    p = Particle(random.randint(0, WIDTH), random.randint(0, HEIGHT),
                 color=type_info["color"],
                 radius=type_info["radius"],
                 rules=type_info["rules"])
    particles.append(p)

# ------------------ Main Loop ------------------
running = True
while running:
    clock.tick(FPS)
    screen.fill((0, 0, 0))

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.MOUSEBUTTONDOWN:
            mouse_x, mouse_y = pygame.mouse.get_pos()
            type_name = random.choice(list(PARTICLE_TYPES.keys()))
            type_info = PARTICLE_TYPES[type_name]
            p = Particle(mouse_x, mouse_y,
                         color=type_info["color"],
                         radius=type_info["radius"],
                         rules=type_info["rules"])
            particles.append(p)

    # Update particles
    for particle in particles:
        particle.update(particles)

    # Draw particles
    for particle in particles:
        particle.draw(screen)

    pygame.display.flip()

pygame.quit()
