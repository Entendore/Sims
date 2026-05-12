import pygame
import random
import sys
import math
from collections import defaultdict

# ============================================================
# CONFIGURATION & CONSTANTS
# ============================================================
SCREEN_WIDTH = 1400
SCREEN_HEIGHT = 850
CHART_HEIGHT = 220
SIMULATION_HEIGHT = SCREEN_HEIGHT - CHART_HEIGHT

# Colors
COLOR_BG = (12, 12, 22)
COLOR_SUSCEPTIBLE = (100, 149, 237)
COLOR_INFECTED = (255, 50, 50)
COLOR_RECOVERED = (50, 205, 50)
COLOR_VACCINATED = (0, 210, 210)
COLOR_DEAD = (120, 120, 120)
COLOR_QUARANTINE_RING = (255, 165, 0)
COLOR_TEXT = (225, 225, 235)
COLOR_TEXT_DIM = (130, 130, 150)
COLOR_GRAPH_BG = (18, 18, 28)
COLOR_GRID = (35, 35, 50)
COLOR_BORDER = (55, 55, 75)
COLOR_BUTTON = (40, 40, 60)
COLOR_BUTTON_HOVER = (60, 60, 90)
COLOR_BUTTON_ACTIVE = (40, 105, 50)
COLOR_HIGHLIGHT = (255, 255, 80)
COLOR_PANEL_OVERLAY = (15, 15, 25, 185)
COLOR_MASK_DOT = (220, 220, 240)
COLOR_CAMPAIGN = (180, 130, 255)
COLOR_SUPERSPREAD = (255, 80, 200)

# Defaults
DEFAULT_POPULATION = 400
DEFAULT_INITIAL_INFECTED = 3
DEFAULT_INFECTION_RADIUS = 12
DEFAULT_INFECTION_PROB = 0.025
DEFAULT_RECOVERY_TIME = 500
DEFAULT_MORTALITY_RATE = 0.015
DEFAULT_PERSON_RADIUS = 3
DEFAULT_SPEED = 1.0
DEFAULT_QUARANTINE_DELAY = 200
DEFAULT_MASK_EFFICACY = 0.6
DEFAULT_SOCIAL_DIST_RADIUS = 30
DEFAULT_SOCIAL_DIST_FORCE = 0.05
DEFAULT_WANING_TIME = 4000
DEFAULT_HOSPITAL_CAPACITY = 50
DEFAULT_VACC_CAMPAIGN_RATE = 0.001  # fraction of susceptible per frame

CHART_HISTORY_LENGTH = 800
GRID_CELL_SIZE = 30


# ============================================================
# SPATIAL HASH GRID — O(n) neighbor lookups
# ============================================================
class SpatialGrid:
    def __init__(self, cell_size, width, height):
        self.cell_size = cell_size
        self.cells = defaultdict(list)

    def clear(self):
        self.cells.clear()

    def insert(self, person):
        cx = int(person.x // self.cell_size)
        cy = int(person.y // self.cell_size)
        self.cells[(cx, cy)].append(person)

    def query(self, x, y, radius):
        result = []
        r = int(radius // self.cell_size) + 1
        cx = int(x // self.cell_size)
        cy = int(y // self.cell_size)
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                bucket = self.cells.get((cx + dx, cy + dy))
                if bucket:
                    result.extend(bucket)
        return result


# ============================================================
# PERSON
# ============================================================
class Person:
    __slots__ = [
        'x', 'y', 'vx', 'vy', 'status', 'infection_timer',
        'radius', 'has_mask', 'quarantine_timer', 'immunity_timer',
        'infections_caused', 'is_quarantined',
    ]

    STATUS_COLORS = {
        "susceptible": COLOR_SUSCEPTIBLE,
        "infected": COLOR_INFECTED,
        "recovered": COLOR_RECOVERED,
        "vaccinated": COLOR_VACCINATED,
        "dead": COLOR_DEAD,
    }

    def __init__(self, x, y, speed=DEFAULT_SPEED):
        self.x = float(x)
        self.y = float(y)
        angle = random.uniform(0, 2 * math.pi)
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.status = "susceptible"
        self.infection_timer = 0
        self.radius = DEFAULT_PERSON_RADIUS
        self.has_mask = False
        self.quarantine_timer = 0
        self.immunity_timer = 0
        self.infections_caused = 0
        self.is_quarantined = False

    def infect(self):
        if self.status == "susceptible":
            self.status = "infected"
            self.infection_timer = 0
            self.quarantine_timer = 0
            self.is_quarantined = False
            return True
        return False

    def vaccinate(self):
        if self.status == "susceptible":
            self.status = "vaccinated"
            self.immunity_timer = 0
            return True
        return False

    def update(self, params, infected_count, spatial_grid):
        self._move(params, spatial_grid)

        if self.status == "infected":
            self.infection_timer += 1

            # Quarantine detection
            if params.quarantine_enabled and not self.is_quarantined:
                self.quarantine_timer += 1
                if self.quarantine_timer >= params.quarantine_delay:
                    if random.random() < 0.6:
                        self.is_quarantined = True

            # Recovery or death
            if self.infection_timer >= params.recovery_time:
                mortality = params.mortality_rate
                if infected_count > params.hospital_capacity:
                    mortality *= 2.5
                if random.random() < mortality:
                    self.status = "dead"
                    self.is_quarantined = False
                else:
                    self.status = "recovered"
                    self.immunity_timer = 0
                    self.is_quarantined = False

        elif self.status in ("recovered", "vaccinated"):
            if params.immunity_waning:
                self.immunity_timer += 1
                wane = params.waning_time if self.status == "recovered" else int(params.waning_time * 1.5)
                if self.immunity_timer >= wane:
                    self.status = "susceptible"

    def _move(self, params, spatial_grid):
        if self.status == "dead" or self.is_quarantined:
            return

        # Lockdown: nearly frozen
        if params.lockdown and self.status != "infected":
            self.vx *= 0.92
            self.vy *= 0.92
            self.x += self.vx * 0.08
            self.y += self.vy * 0.08
            self._clamp()
            return

        # Social distancing repulsion
        if params.social_distancing and self.status != "infected":
            nearby = spatial_grid.query(self.x, self.y, params.social_dist_radius)
            rx, ry = 0.0, 0.0
            for other in nearby:
                if other is not self:
                    dx = self.x - other.x
                    dy = self.y - other.y
                    d2 = dx * dx + dy * dy
                    if 0 < d2 < params.social_dist_radius ** 2:
                        d = math.sqrt(d2)
                        f = params.social_dist_force / d
                        rx += dx * f
                        ry += dy * f
            self.vx += rx
            self.vy += ry

        # Brownian jitter
        self.vx += random.gauss(0, 0.05)
        self.vy += random.gauss(0, 0.05)

        # Speed cap
        spd = math.hypot(self.vx, self.vy)
        max_spd = params.speed * (1.3 if self.status == "infected" else 1.0)
        if spd > max_spd:
            ratio = max_spd / spd
            self.vx *= ratio
            self.vy *= ratio

        self.x += self.vx
        self.y += self.vy
        self._clamp()

    def _clamp(self):
        r = self.radius
        if self.x < r:
            self.x = r
            self.vx = abs(self.vx)
        elif self.x > SCREEN_WIDTH - r:
            self.x = SCREEN_WIDTH - r
            self.vx = -abs(self.vx)
        if self.y < r:
            self.y = r
            self.vy = abs(self.vy)
        elif self.y > SIMULATION_HEIGHT - r:
            self.y = SIMULATION_HEIGHT - r
            self.vy = -abs(self.vy)

    def draw(self, surface, show_radius=False, inf_radius=0):
        ix, iy = int(self.x), int(self.y)

        if self.status == "dead":
            s = self.radius + 2
            pygame.draw.line(surface, COLOR_DEAD, (ix - s, iy - s), (ix + s, iy + s), 2)
            pygame.draw.line(surface, COLOR_DEAD, (ix + s, iy - s), (ix - s, iy + s), 2)
            return

        # Infection radius halo
        if show_radius and self.status == "infected" and not self.is_quarantined:
            halo = pygame.Surface((inf_radius * 2, inf_radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(halo, (*COLOR_INFECTED, 18), (inf_radius, inf_radius), inf_radius)
            pygame.draw.circle(halo, (*COLOR_INFECTED, 40), (inf_radius, inf_radius), inf_radius, 1)
            surface.blit(halo, (ix - inf_radius, iy - inf_radius))

        # Quarantine ring
        if self.is_quarantined:
            pygame.draw.circle(surface, COLOR_QUARANTINE_RING, (ix, iy), self.radius + 5, 1)

        # Main dot
        color = self.STATUS_COLORS[self.status]
        pygame.draw.circle(surface, color, (ix, iy), self.radius)

        # Mask indicator
        if self.has_mask:
            pygame.draw.circle(surface, COLOR_MASK_DOT, (ix, iy - self.radius - 2), 1)


# ============================================================
# SIMULATION PARAMETERS
# ============================================================
class SimParams:
    def __init__(self):
        self.population_size = DEFAULT_POPULATION
        self.infection_radius = DEFAULT_INFECTION_RADIUS
        self.infection_prob = DEFAULT_INFECTION_PROB
        self.recovery_time = DEFAULT_RECOVERY_TIME
        self.mortality_rate = DEFAULT_MORTALITY_RATE
        self.speed = DEFAULT_SPEED
        self.hospital_capacity = DEFAULT_HOSPITAL_CAPACITY

        self.quarantine_enabled = False
        self.quarantine_delay = DEFAULT_QUARANTINE_DELAY
        self.mask_enabled = False
        self.mask_efficacy = DEFAULT_MASK_EFFICACY
        self.lockdown = False
        self.social_distancing = False
        self.social_dist_radius = DEFAULT_SOCIAL_DIST_RADIUS
        self.social_dist_force = DEFAULT_SOCIAL_DIST_FORCE
        self.immunity_waning = False
        self.waning_time = DEFAULT_WANING_TIME

        self.vacc_campaign = False
        self.vacc_campaign_rate = DEFAULT_VACC_CAMPAIGN_RATE

        self.show_infection_radius = False
        self.paused = False
        self.sim_speed = 1


# ============================================================
# UI BUTTON
# ============================================================
class Button:
    def __init__(self, x, y, w, h, label, toggle=False, active=False):
        self.rect = pygame.Rect(x, y, w, h)
        self.label = label
        self.toggle = toggle
        self.active = active
        self.hovered = False

    def draw(self, surface, font):
        if self.active:
            bg = COLOR_BUTTON_ACTIVE
        elif self.hovered:
            bg = COLOR_BUTTON_HOVER
        else:
            bg = COLOR_BUTTON
        pygame.draw.rect(surface, bg, self.rect, border_radius=5)
        pygame.draw.rect(surface, COLOR_BORDER, self.rect, 1, border_radius=5)
        txt = font.render(self.label, True, COLOR_TEXT)
        surface.blit(txt, (self.rect.centerx - txt.get_width() // 2,
                           self.rect.centery - txt.get_height() // 2))

    def update_hover(self, pos):
        self.hovered = self.rect.collidepoint(pos)

    def click(self, pos):
        if self.rect.collidepoint(pos):
            if self.toggle:
                self.active = not self.active
            return True
        return False


# ============================================================
# CHART DRAWING
# ============================================================
def draw_chart(surface, history, pop_size, font):
    if len(history) < 2:
        return

    chart_rect = pygame.Rect(70, SIMULATION_HEIGHT + 40, SCREEN_WIDTH - 220, CHART_HEIGHT - 65)
    pygame.draw.rect(surface, COLOR_GRAPH_BG, chart_rect, border_radius=4)

    # Grid + Y labels
    for i in range(5):
        y = chart_rect.top + i * chart_rect.height // 4
        pygame.draw.line(surface, COLOR_GRID, (chart_rect.left, y), (chart_rect.right, y))
        val = int(pop_size * (1 - i / 4))
        lbl = font.render(str(val), True, COLOR_TEXT_DIM)
        surface.blit(lbl, (chart_rect.left - lbl.get_width() - 5, y - lbl.get_height() // 2))

    # Axes
    pygame.draw.line(surface, COLOR_TEXT_DIM, (chart_rect.left, chart_rect.bottom),
                     (chart_rect.right, chart_rect.bottom))
    pygame.draw.line(surface, COLOR_TEXT_DIM, (chart_rect.left, chart_rect.top),
                     (chart_rect.left, chart_rect.bottom))

    # Layers for filled area chart: bottom to top
    # Order: susceptible(0), vaccinated(3), recovered(2), infected(1), dead(4)
    stack_map = [0, 3, 2, 1, 4]
    layer_colors = [COLOR_SUSCEPTIBLE, COLOR_VACCINATED, COLOR_RECOVERED, COLOR_INFECTED, COLOR_DEAD]

    n = len(history)
    cum_data = []
    for rec in history:
        layers = [rec[si] for si in stack_map]
        cum, cum_vals = 0, []
        for v in layers:
            cum += v
            cum_vals.append(cum)
        cum_data.append(cum_vals)

    # Draw filled areas + lines on an alpha surface
    chart_surf = pygame.Surface((chart_rect.width, chart_rect.height), pygame.SRCALPHA)

    for li in range(len(layer_colors) - 1, -1, -1):
        col = layer_colors[li]
        top_pts = []
        bot_pts = []
        for idx in range(n):
            x = (idx / CHART_HISTORY_LENGTH) * chart_rect.width
            y_top = chart_rect.height - (cum_data[idx][li] / pop_size) * chart_rect.height
            if li > 0:
                y_bot = chart_rect.height - (cum_data[idx][li - 1] / pop_size) * chart_rect.height
            else:
                y_bot = chart_rect.height
            top_pts.append((x, y_top))
            bot_pts.append((x, y_bot))

        if len(top_pts) >= 2:
            poly = top_pts + list(reversed(bot_pts))
            try:
                pygame.draw.polygon(chart_surf, (*col, 55), poly)
            except ValueError:
                pass
            pygame.draw.lines(chart_surf, (*col, 220), False, top_pts, 2)

    surface.blit(chart_surf, chart_rect.topleft)

    # Legend with current counts
    last = history[-1]
    legend_items = [
        ("Susceptible", COLOR_SUSCEPTIBLE, last[0]),
        ("Infected", COLOR_INFECTED, last[1]),
        ("Recovered", COLOR_RECOVERED, last[2]),
        ("Vaccinated", COLOR_VACCINATED, last[3]),
        ("Dead", COLOR_DEAD, last[4]),
    ]
    lx = chart_rect.right + 15
    for i, (name, col, cnt) in enumerate(legend_items):
        ly = chart_rect.top + 5 + i * 22
        pygame.draw.rect(surface, col, (lx, ly + 2, 12, 12), border_radius=2)
        t = font.render(f"{name}: {cnt}", True, COLOR_TEXT)
        surface.blit(t, (lx + 18, ly))


# ============================================================
# FLASH EFFECTS (for superspreader events)
# ============================================================
class FlashEffect:
    def __init__(self, x, y, radius, color, duration=30):
        self.x = x
        self.y = y
        self.radius = radius
        self.color = color
        self.duration = duration
        self.timer = 0

    def update(self):
        self.timer += 1
        return self.timer < self.duration

    def draw(self, surface):
        alpha = max(0, int(180 * (1 - self.timer / self.duration)))
        r = int(self.radius * (1 + 0.5 * self.timer / self.duration))
        if r > 0 and alpha > 0:
            s = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(s, (*self.color, alpha), (r, r), r, 3)
            surface.blit(s, (int(self.x) - r, int(self.y) - r))


# ============================================================
# MAIN SIMULATION
# ============================================================
def run_simulation():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Virus Outbreak Simulation — Enhanced")
    clock = pygame.time.Clock()

    font_tiny = pygame.font.Font(None, 18)
    font_small = pygame.font.Font(None, 22)
    font_med = pygame.font.Font(None, 26)
    font_large = pygame.font.Font(None, 34)

    params = SimParams()
    grid = SpatialGrid(GRID_CELL_SIZE, SCREEN_WIDTH, SIMULATION_HEIGHT)
    chart_history = []
    flash_effects = []

    # Tracking stats
    frame_count = 0
    day_counter = 0
    peak_infected = 0
    total_ever_infected = 0
    r0_estimates = []

    # Population
    population = []
    for _ in range(params.population_size):
        x = random.randint(15, SCREEN_WIDTH - 15)
        y = random.randint(15, SIMULATION_HEIGHT - 15)
        population.append(Person(x, y, params.speed))

    for i in range(DEFAULT_INITIAL_INFECTED):
        if i < len(population):
            population[i].infect()
            total_ever_infected += 1

    # --- UI Buttons ---
    bx, by = 12, 12
    bw, bh, gap = 155, 26, 30

    toggle_btns = {}
    toggle_defs = [
        ('quarantine', "Quarantine [Q]"),
        ('masks', "Masks [M]"),
        ('distancing', "Soc. Distancing [S]"),
        ('lockdown', "Lockdown [L]"),
        ('waning', "Imm. Waning [W]"),
        ('show_radius', "Show Radius [I]"),
        ('vacc_campaign', "Vacc. Campaign [C]"),
    ]
    for i, (key, label) in enumerate(toggle_defs):
        toggle_btns[key] = Button(bx, by + i * gap, bw, bh, label, toggle=True)

    action_y = by + len(toggle_defs) * gap + 12
    action_btns = {}
    action_defs = [
        ('vaccinate', "Vaccinate 10% [V]"),
        ('superspreader', "Super-Spread [E]"),
        ('reset', "Reset [R]"),
    ]
    for i, (key, label) in enumerate(action_defs):
        action_btns[key] = Button(bx, action_y + i * gap, bw, bh, label)

    all_btns = {**toggle_btns, **action_btns}

    # Sync helper
    def sync_params_from_buttons():
        params.quarantine_enabled = toggle_btns['quarantine'].active
        params.mask_enabled = toggle_btns['masks'].active
        params.social_distancing = toggle_btns['distancing'].active
        params.lockdown = toggle_btns['lockdown'].active
        params.immunity_waning = toggle_btns['waning'].active
        params.show_infection_radius = toggle_btns['show_radius'].active
        params.vacc_campaign = toggle_btns['vacc_campaign'].active
        # Apply/remove masks
        for p in population:
            p.has_mask = params.mask_enabled and p.status != "dead"

    def do_vaccinate_10pct():
        sus = [p for p in population if p.status == "susceptible"]
        n = max(1, int(len(sus) * 0.10))
        for p in random.sample(sus, min(n, len(sus))):
            p.vaccinate()

    def do_superspreader():
        sx = random.randint(80, SCREEN_WIDTH - 80)
        sy = random.randint(80, SIMULATION_HEIGHT - 80)
        count = 0
        for p in population:
            if p.status == "susceptible":
                d = math.hypot(p.x - sx, p.y - sy)
                if d < 70 and random.random() < 0.6:
                    if p.infect():
                        total_ever_infected += 1
                        count += 1
        flash_effects.append(FlashEffect(sx, sy, 70, COLOR_SUPERSPREAD, 40))
        return count

    def do_reset():
        nonlocal population, chart_history, flash_effects
        nonlocal frame_count, day_counter, peak_infected, total_ever_infected, r0_estimates
        chart_history.clear()
        flash_effects.clear()
        frame_count = 0
        day_counter = 0
        peak_infected = 0
        total_ever_infected = 0
        r0_estimates.clear()

        population = []
        for _ in range(params.population_size):
            x = random.randint(15, SCREEN_WIDTH - 15)
            y = random.randint(15, SIMULATION_HEIGHT - 15)
            population.append(Person(x, y, params.speed))
        for i in range(DEFAULT_INITIAL_INFECTED):
            if i < len(population):
                population[i].infect()
                total_ever_infected += 1

        for p in population:
            p.has_mask = params.mask_enabled

    # ============================================================
    # MAIN LOOP
    # ============================================================
    running = True
    while running:
        mouse_pos = pygame.mouse.get_pos()

        # --- EVENTS ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    params.paused = not params.paused
                elif event.key == pygame.K_UP:
                    params.infection_prob = min(0.15, params.infection_prob + 0.005)
                elif event.key == pygame.K_DOWN:
                    params.infection_prob = max(0.0, params.infection_prob - 0.005)
                elif event.key == pygame.K_RIGHT:
                    params.infection_radius = min(60, params.infection_radius + 2)
                elif event.key == pygame.K_LEFT:
                    params.infection_radius = max(3, params.infection_radius - 2)
                elif event.key == pygame.K_v:
                    do_vaccinate_10pct()
                elif event.key == pygame.K_e:
                    do_superspreader()
                elif event.key == pygame.K_s:
                    toggle_btns['distancing'].active = not toggle_btns['distancing'].active
                    sync_params_from_buttons()
                elif event.key == pygame.K_q:
                    toggle_btns['quarantine'].active = not toggle_btns['quarantine'].active
                    sync_params_from_buttons()
                elif event.key == pygame.K_m:
                    toggle_btns['masks'].active = not toggle_btns['masks'].active
                    sync_params_from_buttons()
                elif event.key == pygame.K_l:
                    toggle_btns['lockdown'].active = not toggle_btns['lockdown'].active
                    sync_params_from_buttons()
                elif event.key == pygame.K_w:
                    toggle_btns['waning'].active = not toggle_btns['waning'].active
                    sync_params_from_buttons()
                elif event.key == pygame.K_i:
                    toggle_btns['show_radius'].active = not toggle_btns['show_radius'].active
                    sync_params_from_buttons()
                elif event.key == pygame.K_c:
                    toggle_btns['vacc_campaign'].active = not toggle_btns['vacc_campaign'].active
                    sync_params_from_buttons()
                elif event.key == pygame.K_r:
                    do_reset()
                elif event.key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
                    params.sim_speed = min(8, params.sim_speed * 2)
                elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    params.sim_speed = max(1, params.sim_speed // 2)

            elif event.type == pygame.MOUSEBUTTONDOWN:
                clicked_btn = False
                for btn in all_btns.values():
                    if btn.click(mouse_pos):
                        clicked_btn = True
                        sync_params_from_buttons()
                        if btn is action_btns['vaccinate']:
                            do_vaccinate_10pct()
                        elif btn is action_btns['superspreader']:
                            do_superspreader()
                        elif btn is action_btns['reset']:
                            do_reset()
                        break

                if not clicked_btn and mouse_pos[1] < SIMULATION_HEIGHT and mouse_pos[0] > bx + bw + 10:
                    if event.button == 1:
                        # Left click: infect nearest susceptible
                        best, best_d = None, 25
                        for p in population:
                            if p.status == "susceptible":
                                d = math.hypot(p.x - mouse_pos[0], p.y - mouse_pos[1])
                                if d < best_d:
                                    best, best_d = p, d
                        if best and best.infect():
                            total_ever_infected += 1
                            flash_effects.append(FlashEffect(best.x, best.y, 15, COLOR_INFECTED, 20))
                    elif event.button == 3:
                        # Right click: vaccinate nearest susceptible
                        best, best_d = None, 25
                        for p in population:
                            if p.status == "susceptible":
                                d = math.hypot(p.x - mouse_pos[0], p.y - mouse_pos[1])
                                if d < best_d:
                                    best, best_d = p, d
                        if best and best.vaccinate():
                            flash_effects.append(FlashEffect(best.x, best.y, 15, COLOR_VACCINATED, 20))

        # Hover
        for btn in all_btns.values():
            btn.update_hover(mouse_pos)

        # --- SIMULATION UPDATE ---
        if not params.paused:
            for _ in range(params.sim_speed):
                frame_count += 1
                day_counter = frame_count // 60

                # Rebuild spatial grid
                grid.clear()
                for p in population:
                    grid.insert(p)

                # Count infected (for hospital capacity)
                infected_count = 0
                for p in population:
                    if p.status == "infected":
                        infected_count += 1

                # Update all
                for p in population:
                    p.update(params, infected_count, grid)

                # Infection spreading
                for p in population:
                    if p.status == "infected" and not p.is_quarantined:
                        nearby = grid.query(p.x, p.y, params.infection_radius)
                        for other in nearby:
                            if other is not p and other.status == "susceptible":
                                dx = p.x - other.x
                                dy = p.y - other.y
                                if dx * dx + dy * dy < params.infection_radius ** 2:
                                    prob = params.infection_prob
                                    if p.has_mask:
                                        prob *= (1 - params.mask_efficacy * 0.5)
                                    if other.has_mask:
                                        prob *= (1 - params.mask_efficacy)
                                    if random.random() < prob:
                                        if other.infect():
                                            p.infections_caused += 1
                                            total_ever_infected += 1

                # Auto vaccination campaign
                if params.vacc_campaign:
                    sus = [p for p in population if p.status == "susceptible"]
                    n = max(1, int(len(sus) * params.vacc_campaign_rate))
                    if sus and n > 0:
                        for p in random.sample(sus, min(n, len(sus))):
                            p.vaccinate()

                # Count for chart
                s_c = i_c = r_c = v_c = d_c = 0
                for p in population:
                    if p.status == "susceptible":
                        s_c += 1
                    elif p.status == "infected":
                        i_c += 1
                    elif p.status == "recovered":
                        r_c += 1
                    elif p.status == "vaccinated":
                        v_c += 1
                    elif p.status == "dead":
                        d_c += 1

                if i_c > peak_infected:
                    peak_infected = i_c

                # R0 estimate
                resolved = [p for p in population if p.status in ("recovered", "dead")]
                if len(resolved) > 5:
                    avg_r = sum(p.infections_caused for p in resolved) / len(resolved)
                    r0_estimates.append(avg_r)
                    if len(r0_estimates) > 200:
                        r0_estimates.pop(0)

                chart_history.append((s_c, i_c, r_c, v_c, d_c))
                if len(chart_history) > CHART_HISTORY_LENGTH:
                    chart_history.pop(0)

        # Update flash effects
        flash_effects = [f for f in flash_effects if f.update()]

        # --- DRAWING ---
        screen.fill(COLOR_BG)

        # Simulation area
        sim_rect = pygame.Rect(0, 0, SCREEN_WIDTH, SIMULATION_HEIGHT)
        pygame.draw.rect(screen, COLOR_BG, sim_rect)

        # Draw flash effects (behind people)
        for f in flash_effects:
            f.draw(screen)

        # Draw people
        for p in population:
            p.draw(screen, params.show_infection_radius, params.infection_radius)

        # Panel overlay
        panel_w = bx + bw + 15
        panel_surf = pygame.Surface((panel_w, SIMULATION_HEIGHT), pygame.SRCALPHA)
        panel_surf.fill(COLOR_PANEL_OVERLAY)
        screen.blit(panel_surf, (0, 0))
        pygame.draw.line(screen, COLOR_BORDER, (panel_w, 0), (panel_w, SIMULATION_HEIGHT))

        # Buttons
        for btn in all_btns.values():
            btn.draw(screen, font_tiny)

        # Stats section
        if chart_history:
            s_c, i_c, r_c, v_c, d_c = chart_history[-1]
        else:
            s_c = i_c = r_c = v_c = d_c = 0
        q_c = sum(1 for p in population if p.is_quarantined)

        sy = action_y + len(action_defs) * gap + 15
        pygame.draw.line(screen, COLOR_BORDER, (bx, sy - 5), (bx + bw, sy - 5))
        stat_title = font_small.render("— Statistics —", True, COLOR_TEXT)
        screen.blit(stat_title, (bx + bw // 2 - stat_title.get_width() // 2, sy))
        sy += 25

        stat_lines = [
            (f"Susceptible: {s_c}", COLOR_SUSCEPTIBLE),
            (f"Infected: {i_c}", COLOR_INFECTED),
            (f"Recovered: {r_c}", COLOR_RECOVERED),
            (f"Vaccinated: {v_c}", COLOR_VACCINATED),
            (f"Dead: {d_c}", COLOR_DEAD),
            (f"Quarantined: {q_c}", COLOR_QUARANTINE_RING),
        ]
        for i, (txt, col) in enumerate(stat_lines):
            pygame.draw.circle(screen, col, (bx + 6, sy + i * 20 + 6), 4)
            t = font_tiny.render(txt, True, COLOR_TEXT)
            screen.blit(t, (bx + 16, sy + i * 20 - 2))

        sy += len(stat_lines) * 20 + 10
        pygame.draw.line(screen, COLOR_BORDER, (bx, sy), (bx + bw, sy))
        sy += 8

        r0_val = r0_estimates[-1] if r0_estimates else 0
        info_lines = [
            (f"Day: {day_counter}", COLOR_TEXT),
            (f"Peak Infected: {peak_infected}", COLOR_HIGHLIGHT),
            (f"Total Infected: {total_ever_infected}", COLOR_TEXT_DIM),
            (f"R estimate: {r0_val:.2f}", COLOR_HIGHLIGHT if r0_val > 1 else COLOR_RECOVERED),
            (f"Hospital Cap: {params.hospital_capacity}", COLOR_TEXT_DIM),
        ]
        for i, (txt, col) in enumerate(info_lines):
            t = font_tiny.render(txt, True, col)
            screen.blit(t, (bx, sy + i * 18))

        sy += len(info_lines) * 18 + 10
        pygame.draw.line(screen, COLOR_BORDER, (bx, sy), (bx + bw, sy))
        sy += 8

        param_lines = [
            f"Speed: {params.sim_speed}x",
            f"Prob: {params.infection_prob:.3f}",
            f"Radius: {params.infection_radius}",
            f"Mortality: {params.mortality_rate:.3f}",
        ]
        for i, txt in enumerate(param_lines):
            t = font_tiny.render(txt, True, COLOR_TEXT_DIM)
            screen.blit(t, (bx, sy + i * 18))

        # Paused / Running indicator
        sy += len(param_lines) * 18 + 10
        if params.paused:
            status_txt = font_med.render("⏸ PAUSED", True, COLOR_HIGHLIGHT)
        else:
            status_txt = font_med.render("▶ RUNNING", True, COLOR_RECOVERED)
        screen.blit(status_txt, (bx + bw // 2 - status_txt.get_width() // 2, sy))

        # Help at bottom of panel
        help_y = SIMULATION_HEIGHT - 110
        pygame.draw.line(screen, COLOR_BORDER, (bx, help_y - 5), (bx + bw, help_y - 5))
        help_title = font_tiny.render("— Controls —", True, COLOR_TEXT_DIM)
        screen.blit(help_title, (bx + bw // 2 - help_title.get_width() // 2, help_y))
        help_lines = [
            "Left-click: Infect person",
            "Right-click: Vaccinate person",
            "Space: Pause/Resume",
            "+/-: Simulation speed",
            "↑↓: Infection prob.",
            "←→: Infection radius",
        ]
        for i, h in enumerate(help_lines):
            t = font_tiny.render(h, True, COLOR_TEXT_DIM)
            screen.blit(t, (bx, help_y + 18 + i * 15))

        # --- CHART AREA ---
        pygame.draw.line(screen, COLOR_BORDER, (0, SIMULATION_HEIGHT), (SCREEN_WIDTH, SIMULATION_HEIGHT), 2)

        chart_title = font_med.render("Population Over Time (Stacked Area)", True, COLOR_TEXT)
        screen.blit(chart_title, (70, SIMULATION_HEIGHT + 10))

        day_label = font_small.render(f"Day {day_counter}  |  Speed {params.sim_speed}x", True, COLOR_TEXT_DIM)
        screen.blit(day_label, (SCREEN_WIDTH - day_label.get_width() - 20, SIMULATION_HEIGHT + 14))

        draw_chart(screen, chart_history, params.population_size, font_tiny)

        # Title bar at very top of sim area
        title_surf = font_large.render("Virus Outbreak Simulation", True, COLOR_TEXT)
        title_bg = pygame.Surface((title_surf.get_width() + 20, title_surf.get_height() + 6), pygame.SRCALPHA)
        title_bg.fill((12, 12, 22, 160))
        screen.blit(title_bg, (SCREEN_WIDTH // 2 - title_surf.get_width() // 2 - 10, SIMULATION_HEIGHT - 38))
        screen.blit(title_surf, (SCREEN_WIDTH // 2 - title_surf.get_width() // 2, SIMULATION_HEIGHT - 36))

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
    sys.exit()


if __name__ == '__main__':
    run_simulation()