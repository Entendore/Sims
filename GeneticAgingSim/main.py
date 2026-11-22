import pygame
import random
import sys

# --- Configuration & Constants ---
SCREEN_WIDTH = 1200  # Wider screen for the chart
SCREEN_HEIGHT = 700
STATS_HEIGHT = 200   # Taller area for the chart
SIMULATION_HEIGHT = SCREEN_HEIGHT - STATS_HEIGHT

# Colors
COLOR_BACKGROUND = (20, 20, 30)
COLOR_SUSCEPTIBLE = (100, 149, 237)  # Cornflower Blue
COLOR_INFECTED = (220, 20, 60)       # Crimson
COLOR_RECOVERED = (50, 205, 50)      # Lime Green
COLOR_VACCINATED = (0, 255, 255)     # Cyan
COLOR_TEXT = (220, 220, 220)
COLOR_GRAPH_BG = (40, 40, 50)
COLOR_GRID = (60, 60, 70)

# Simulation Parameters
POPULATION_SIZE = 500
INITIAL_INFECTED = 3
INFECTION_RADIUS = 10
INFECTION_PROBABILITY = 0.02
RECOVERY_TIME = 500
PERSON_RADIUS = 3
SPEED = 1

# Social Distancing Parameters
SOCIAL_DISTANCING_ON = False
SOCIAL_DISTANCING_RADIUS = 25
SOCIAL_DISTANCING_FORCE = 0.05

# --- Chart Parameters ---
CHART_HISTORY_LENGTH = 600 # Number of data points to show
chart_history = [] # List to store historical data

# --- The Person Class ---
class Person:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.vx = random.uniform(-SPEED, SPEED)
        self.vy = random.uniform(-SPEED, SPEED)
        self.status = "susceptible"
        self.infection_timer = 0
        self.radius = PERSON_RADIUS

    def move(self):
        if SOCIAL_DISTANCING_ON and self.status != "infected":
            repulsion_x, repulsion_y = 0, 0
            for other in population:
                if other is not self:
                    dx = self.x - other.x
                    dy = self.y - other.y
                    distance_sq = dx**2 + dy**2
                    if distance_sq < SOCIAL_DISTANCING_RADIUS**2 and distance_sq > 0:
                        distance = distance_sq**0.5
                        force = SOCIAL_DISTANCING_FORCE / distance
                        repulsion_x += dx * force
                        repulsion_y += dy * force
            self.vx += repulsion_x
            self.vy += repulsion_y
            current_speed = (self.vx**2 + self.vy**2)**0.5
            if current_speed > SPEED * 2:
                self.vx = (self.vx / current_speed) * SPEED * 2
                self.vy = (self.vy / current_speed) * SPEED * 2

        self.x += self.vx
        self.y += self.vy
        if self.x <= self.radius or self.x >= SCREEN_WIDTH - self.radius: self.vx *= -1
        if self.y <= self.radius or self.y >= SIMULATION_HEIGHT - self.radius: self.vy *= -1

    def infect(self):
        if self.status == "susceptible":
            self.status = "infected"
            self.infection_timer = 0

    def vaccinate(self):
        if self.status == "susceptible":
            self.status = "vaccinated"

    def update(self):
        self.move()
        if self.status == "infected":
            self.infection_timer += 1
            if self.infection_timer >= RECOVERY_TIME:
                self.status = "recovered"

    def draw(self, screen):
        color = {"susceptible": COLOR_SUSCEPTIBLE, "infected": COLOR_INFECTED, 
                 "recovered": COLOR_RECOVERED, "vaccinated": COLOR_VACCINATED}[self.status]
        pygame.draw.circle(screen, color, (int(self.x), int(self.y)), self.radius)

# --- NEW: Chart Drawing Function ---
def draw_chart(screen, history):
    if not history:
        return

    chart_rect = pygame.Rect(50, SIMULATION_HEIGHT + 30, SCREEN_WIDTH - 100, STATS_HEIGHT - 60)
    pygame.draw.rect(screen, COLOR_GRAPH_BG, chart_rect)
    
    # Draw grid lines
    for i in range(5):
        y = chart_rect.top + i * (chart_rect.height // 4)
        pygame.draw.line(screen, COLOR_GRID, (chart_rect.left, y), (chart_rect.right, y), 1)
    
    # Draw axes
    pygame.draw.line(screen, COLOR_TEXT, (chart_rect.left, chart_rect.bottom), (chart_rect.right, chart_rect.bottom), 2)
    pygame.draw.line(screen, COLOR_TEXT, (chart_rect.left, chart_rect.top), (chart_rect.left, chart_rect.bottom), 2)

    # Prepare data for plotting
    states = {
        "Susceptible": {"color": COLOR_SUSCEPTIBLE, "data": []},
        "Infected": {"color": COLOR_INFECTED, "data": []},
        "Recovered": {"color": COLOR_RECOVERED, "data": []},
        "Vaccinated": {"color": COLOR_VACCINATED, "data": []},
    }
    
    for record in history:
        states["Susceptible"]["data"].append(record[0])
        states["Infected"]["data"].append(record[1])
        states["Recovered"]["data"].append(record[2])
        states["Vaccinated"]["data"].append(record[3])

    # Plot lines
    for name, state in states.items():
        if len(state["data"]) > 1:
            points = []
            for i, value in enumerate(state["data"]):
                x = chart_rect.left + (i / CHART_HISTORY_LENGTH) * chart_rect.width
                y = chart_rect.bottom - (value / POPULATION_SIZE) * chart_rect.height
                points.append((x, y))
            if len(points) > 1:
                pygame.draw.lines(screen, state["color"], False, points, 2)

    # Draw Legend and Counts
    font = pygame.font.Font(None, 24)
    legend_x = chart_rect.right - 150
    for i, (name, state) in enumerate(states.items()):
        color_rect = pygame.Rect(legend_x, chart_rect.top + 10 + i * 25, 15, 15)
        pygame.draw.rect(screen, state["color"], color_rect)
        count = state["data"][-1] if state["data"] else 0
        text = font.render(f"{name}: {count}", True, COLOR_TEXT)
        screen.blit(text, (color_rect.right + 5, color_rect.top - 2))

# --- Main Simulation Function ---
def run_simulation():
    global population, SOCIAL_DISTANCING_ON, chart_history

    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Virus Outbreak Visualization with Charts")
    clock = pygame.time.Clock()
    font = pygame.font.Font(None, 24)
    title_font = pygame.font.Font(None, 36)

    population = [Person(random.randint(PERSON_RADIUS, SCREEN_WIDTH - PERSON_RADIUS),
                         random.randint(PERSON_RADIUS, SIMULATION_HEIGHT - PERSON_RADIUS)) for _ in range(POPULATION_SIZE)]
    for i in range(INITIAL_INFECTED): population[i].infect()

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False
            elif event.type == pygame.KEYDOWN:
                global INFECTION_PROBABILITY, INFECTION_RADIUS
                if event.key == pygame.K_UP: INFECTION_PROBABILITY = min(0.1, INFECTION_PROBABILITY + 0.005)
                elif event.key == pygame.K_DOWN: INFECTION_PROBABILITY = max(0, INFECTION_PROBABILITY - 0.005)
                elif event.key == pygame.K_RIGHT: INFECTION_RADIUS = min(50, INFECTION_RADIUS + 2)
                elif event.key == pygame.K_LEFT: INFECTION_RADIUS = max(5, INFECTION_RADIUS - 2)
                elif event.key == pygame.K_v:
                    susceptible = [p for p in population if p.status == "susceptible"]
                    num_to_vaccinate = max(1, int(len(susceptible) * 0.10))
                    for person in random.sample(susceptible, num_to_vaccinate): person.vaccinate()
                elif event.key == pygame.K_s: SOCIAL_DISTANCING_ON = not SOCIAL_DISTANCING_ON
                elif event.key == pygame.K_r:
                    chart_history.clear()
                    run_simulation()
                    return

        # Update Logic
        for person in population: person.update()
        for i, infected_person in enumerate(population):
            if infected_person.status == "infected":
                for j, other_person in enumerate(population):
                    if i != j and other_person.status == "susceptible":
                        dx, dy = infected_person.x - other_person.x, infected_person.y - other_person.y
                        if (dx**2 + dy**2)**0.5 < INFECTION_RADIUS:
                            if random.random() < INFECTION_PROBABILITY: other_person.infect()

        # --- Drawing ---
        screen.fill(COLOR_BACKGROUND)
        pygame.draw.line(screen, COLOR_TEXT, (0, SIMULATION_HEIGHT), (SCREEN_WIDTH, SIMULATION_HEIGHT), 2)
        for person in population: person.draw(screen)

        # --- Update and Draw Chart ---
        s_count = sum(1 for p in population if p.status == "susceptible")
        i_count = sum(1 for p in population if p.status == "infected")
        r_count = sum(1 for p in population if p.status == "recovered")
        v_count = sum(1 for p in population if p.status == "vaccinated")
        
        chart_history.append((s_count, i_count, r_count, v_count))
        if len(chart_history) > CHART_HISTORY_LENGTH:
            chart_history.pop(0)
        
        draw_chart(screen, chart_history)

        # Draw UI Text
        title_text = title_font.render("Virus Outbreak Simulation", True, COLOR_TEXT)
        screen.blit(title_text, (SCREEN_WIDTH // 2 - title_text.get_width() // 2, 10))
        
        prob_text = f"Prob: {INFECTION_PROBABILITY:.3f}"
        radius_text = f"Radius: {INFECTION_RADIUS}"
        dist_text = f"Distancing: {'ON' if SOCIAL_DISTANCING_ON else 'OFF'}"
        controls_text = f"[V]accinate | [S]ocial Distancing | [R]estart | [↑↓] {prob_text} | [←→] {radius_text}"
        
        controls_surface = font.render(controls_text, True, COLOR_TEXT)
        screen.blit(controls_surface, (SCREEN_WIDTH // 2 - controls_surface.get_width() // 2, SIMULATION_HEIGHT + 5))
        
        dist_surface = font.render(dist_text, True, COLOR_TEXT)
        screen.blit(dist_surface, (SCREEN_WIDTH // 2 - dist_surface.get_width() // 2, SIMULATION_HEIGHT + 5 + 25))

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
    sys.exit()

if __name__ == '__main__':
    run_simulation()