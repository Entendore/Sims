"""
Virus Mutation & Outbreak Simulator
=====================================
Combines grid-based strain mutation mechanics with agent-based outbreak simulation.

Controls:
    SPACE       Pause / Resume
    V           Vaccinate 10% of susceptible
    S           Toggle social distancing
    Q           Toggle quarantine
    W           Toggle waning immunity
    T           Toggle travel restrictions
    N           Introduce a new random strain
    R           Reset simulation
    UP/DOWN     Adjust simulation speed
    LEFT/RIGHT  Adjust infection radius
    +/-         Adjust global transmissibility
    [/]         Adjust global mutation multiplier
    Left Click  Infect nearest susceptible person
    Right Click Vaccinate nearest susceptible person
    ESC         Quit

Requirements:
    pip install pygame numpy
"""

import pygame
import random
import sys
import math
from collections import defaultdict

# ============================================================
# CONFIGURATION
# ============================================================
SCREEN_WIDTH = 1400
SCREEN_HEIGHT = 900
SIM_WIDTH = 920
SIM_HEIGHT = 660
PANEL_X = SIM_WIDTH + 10
PANEL_WIDTH = SCREEN_WIDTH - PANEL_X - 5
CHART_Y = SIM_HEIGHT + 5
CHART_HEIGHT = SCREEN_HEIGHT - CHART_Y - 5
CHART_X = 10
CHART_WIDTH = SIM_WIDTH - 20

POPULATION_SIZE = 500
INITIAL_INFECTED = 5
INITIAL_STRAINS = 2
MAX_STRAINS = 150

BASE_INFECTION_RADIUS = 14
BASE_INFECTION_PROB = 0.03
RECOVERY_TIME_BASE = 400
PERSON_RADIUS = 3
BASE_SPEED = 1.0
MORTALITY_RATE = 0.02
WANING_IMMUNITY_TIME = 2500

SOCIAL_DIST_RADIUS = 30
SOCIAL_DIST_FORCE = 0.05
VACCINATE_PCT = 0.10

SPATIAL_CELL = 32
FPS = 60
CHART_HISTORY_LEN = 600

# Colors
C_BG = (12, 12, 22)
C_SIM_BG = (8, 8, 18)
C_SUSCEPTIBLE = (90, 140, 230)
C_RECOVERED = (45, 200, 45)
C_VACCINATED = (0, 210, 210)
C_DEAD = (110, 110, 110)
C_TEXT = (215, 215, 215)
C_DIM_TEXT = (140, 140, 160)
C_PANEL_BG = (20, 20, 35)
C_GRAPH_BG = (25, 25, 42)
C_GRID = (45, 45, 62)
C_BORDER = (70, 70, 95)
C_BTN = (50, 50, 75)
C_BTN_HOVER = (70, 70, 100)
C_BTN_ACTIVE = (35, 110, 35)
C_BTN_TEXT = (215, 215, 215)
C_ACCENT = (255, 90, 90)
C_ACCENT2 = (255, 180, 80)
C_QUARANTINE_ZONE = (180, 40, 40)
C_TRAVEL_ZONE = (40, 40, 180)


# ============================================================
# STRAIN SYSTEM
# ============================================================
class Strain:
    _next_id = 1

    def __init__(self, transmissibility=None, mutation_rate=None,
                 severity=None, parent_id=None, color=None):
        self.id = Strain._next_id
        Strain._next_id += 1
        self.transmissibility = (transmissibility
                                 if transmissibility is not None
                                 else 0.02 + random.random() * 0.03)
        self.mutation_rate = (mutation_rate
                              if mutation_rate is not None
                              else 0.001 + random.random() * 0.006)
        self.severity = (severity
                         if severity is not None
                         else 0.7 + random.random() * 0.6)
        self.parent_id = parent_id
        self.color = color if color else self._gen_color()
        self.generation = 0
        self.birth_step = 0
        self.total_infected = 0          # cumulative infections caused

    @classmethod
    def reset(cls):
        cls._next_id = 1

    def _gen_color(self):
        hue = (self.id * 0.618033988749895) % 1.0
        h = hue * 6.0
        c = 0.82
        x = c * (1.0 - abs(h % 2.0 - 1.0))
        if h < 1:   r, g, b = c, x, 0
        elif h < 2: r, g, b = x, c, 0
        elif h < 3: r, g, b = 0, c, x
        elif h < 4: r, g, b = 0, x, c
        elif h < 5: r, g, b = x, 0, c
        else:       r, g, b = c, 0, x
        v = 0.95
        return (min(255, int((r + v - c) * 255)),
                min(255, int((g + v - c) * 255)),
                min(255, int((b + v - c) * 255)))

    def mutate(self, global_mut_mult, step):
        nt = max(0.005, min(0.12,
                self.transmissibility * (1.0 + random.gauss(0, 0.12))))
        nm = max(0.0, min(0.04,
                self.mutation_rate * (1.0 + random.gauss(0, 0.2)) * global_mut_mult))
        ns = max(0.4, min(2.2,
                self.severity * (1.0 + random.gauss(0, 0.10))))
        child = Strain(transmissibility=nt, mutation_rate=nm,
                       severity=ns, parent_id=self.id)
        child.generation = self.generation + 1
        child.birth_step = step
        pr, pg, pb = self.color
        child.color = (
            max(30, min(255, pr + random.randint(-35, 35))),
            max(30, min(255, pg + random.randint(-35, 35))),
            max(30, min(255, pb + random.randint(-35, 35))),
        )
        return child


# ============================================================
# SPATIAL HASH
# ============================================================
class SpatialHash:
    def __init__(self, cell_size):
        self.cs = cell_size
        self.grid = defaultdict(list)

    def clear(self):
        self.grid.clear()

    def insert(self, person):
        key = (int(person.x // self.cs), int(person.y // self.cs))
        self.grid[key].append(person)

    def query(self, x, y, radius):
        out = []
        cs = self.cs
        x0 = int((x - radius) // cs)
        x1 = int((x + radius) // cs)
        y0 = int((y - radius) // cs)
        y1 = int((y + radius) // cs)
        for cx in range(x0, x1 + 1):
            for cy in range(y0, y1 + 1):
                bucket = self.grid.get((cx, cy))
                if bucket:
                    out.extend(bucket)
        return out


# ============================================================
# PERSON
# ============================================================
class Person:
    __slots__ = ('x', 'y', 'vx', 'vy', 'status', 'strain',
                 'inf_timer', 'imm_timer', 'strain_immunity',
                 'alive', 'home_x', 'home_y')

    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.vx = random.uniform(-BASE_SPEED, BASE_SPEED)
        self.vy = random.uniform(-BASE_SPEED, BASE_SPEED)
        self.status = "susceptible"
        self.strain = None
        self.inf_timer = 0
        self.imm_timer = 0
        self.strain_immunity = set()
        self.alive = True
        self.home_x = x
        self.home_y = y

    def move(self, quarantine, speed_mult):
        if not self.alive:
            return
        if quarantine and self.status == "infected":
            if random.random() < 0.92:
                return
        self.x += self.vx * speed_mult
        self.y += self.vy * speed_mult
        r = PERSON_RADIUS
        if self.x < r:      self.x = r;            self.vx = abs(self.vx)
        if self.x > SIM_WIDTH - r:  self.x = SIM_WIDTH - r; self.vx = -abs(self.vx)
        if self.y < r:      self.y = r;            self.vy = abs(self.vy)
        if self.y > SIM_HEIGHT - r: self.y = SIM_HEIGHT - r; self.vy = -abs(self.vy)
        self.vx += random.gauss(0, 0.04) * speed_mult
        self.vy += random.gauss(0, 0.04) * speed_mult
        spd = math.hypot(self.vx, self.vy)
        mx = BASE_SPEED * speed_mult * 2.2
        if spd > mx:
            self.vx = self.vx / spd * mx
            self.vy = self.vy / spd * mx

    def infect(self, strain):
        if self.status == "susceptible" and strain.id not in self.strain_immunity:
            self.status = "infected"
            self.strain = strain
            self.inf_timer = 0
            strain.total_infected += 1
            return True
        return False

    def vaccinate(self):
        if self.status == "susceptible":
            self.status = "vaccinated"
            self.strain_immunity.add(-1)
            return True
        return False

    def update(self, mortality, waning):
        if self.status == "infected":
            self.inf_timer += 1
            rec = int(RECOVERY_TIME_BASE * self.strain.severity)
            if self.inf_timer >= rec:
                if random.random() < mortality:
                    self.status = "dead"
                    self.alive = False
                    self.strain = None
                else:
                    self.status = "recovered"
                    self.strain_immunity.add(self.strain.id)
                    self.imm_timer = 0
                    self.strain = None
        elif self.status == "recovered":
            if waning:
                self.imm_timer += 1
                if self.imm_timer >= WANING_IMMUNITY_TIME:
                    self.status = "susceptible"
                    self.strain_immunity.clear()
                    self.imm_timer = 0

    def color(self):
        if self.status == "susceptible":  return C_SUSCEPTIBLE
        if self.status == "infected":     return self.strain.color if self.strain else C_ACCENT
        if self.status == "recovered":    return C_RECOVERED
        if self.status == "vaccinated":   return C_VACCINATED
        if self.status == "dead":         return C_DEAD
        return C_TEXT

    def draw(self, surf):
        ix, iy = int(self.x), int(self.y)
        if not self.alive:
            pygame.draw.line(surf, C_DEAD, (ix - 2, iy - 2), (ix + 2, iy + 2), 1)
            pygame.draw.line(surf, C_DEAD, (ix - 2, iy + 2), (ix + 2, iy - 2), 1)
        else:
            c = self.color()
            pygame.draw.circle(surf, c, (ix, iy), PERSON_RADIUS)
            if self.status == "infected":
                glow = (min(255, c[0] + 30), min(255, c[1] + 30), min(255, c[2] + 30))
                pygame.draw.circle(surf, glow, (ix, iy), PERSON_RADIUS + 2, 1)


# ============================================================
# BUTTON
# ============================================================
class Button:
    def __init__(self, x, y, w, h, text, cb=None, toggle=False):
        self.rect = pygame.Rect(x, y, w, h)
        self.text = text
        self.cb = cb
        self.toggle = toggle
        self.active = False
        self.hovered = False

    def draw(self, surf, font):
        col = C_BTN_ACTIVE if (self.active and self.toggle) else (C_BTN_HOVER if self.hovered else C_BTN)
        pygame.draw.rect(surf, col, self.rect, border_radius=5)
        pygame.draw.rect(surf, C_BORDER, self.rect, 1, border_radius=5)
        ts = font.render(self.text, True, C_BTN_TEXT)
        surf.blit(ts, ts.get_rect(center=self.rect.center))

    def handle(self, ev):
        if ev.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(ev.pos)
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if self.rect.collidepoint(ev.pos):
                if self.toggle:
                    self.active = not self.active
                if self.cb:
                    self.cb()
                return True
        return False


# ============================================================
# SIMULATION
# ============================================================
class Simulation:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Virus Mutation & Outbreak Simulator")
        self.clock = pygame.time.Clock()
        self.font_s = pygame.font.Font(None, 19)
        self.font_m = pygame.font.Font(None, 23)
        self.font_l = pygame.font.Font(None, 30)
        self.font_xl = pygame.font.Font(None, 38)

        self.sim_surf = pygame.Surface((SIM_WIDTH, SIM_HEIGHT))
        self.sh = SpatialHash(SPATIAL_CELL)

        # Simulation state
        self.step = 0
        self.paused = False
        self.speed = 1.0
        self.inf_radius = BASE_INFECTION_RADIUS
        self.global_trans = 1.0
        self.global_mut = 1.0
        self.mortality = MORTALITY_RATE
        self.waning = False
        self.soc_dist = False
        self.quarantine = False
        self.travel = False
        self.show_radius = False
        self.peak_infected = 0
        self.peak_step = 0
        self.total_ever_infected = 0

        self.strains = []
        self.population = []
        self.chart_hist = []
        self.strain_hist = defaultdict(list)

        self._build_buttons()
        self.reset()

    # --- buttons ---
    def _build_buttons(self):
        bx = PANEL_X + 5
        by = 545
        bw = 137
        bh = 28
        g = 34
        self.btn_sd = Button(bx, by, bw, bh, "Soc. Distancing [S]", self._t_sd, True)
        self.btn_q  = Button(bx+bw+8, by, bw, bh, "Quarantine [Q]", self._t_q, True)
        self.btn_w  = Button(bx, by+g, bw, bh, "Waning Imm. [W]", self._t_w, True)
        self.btn_tr = Button(bx+bw+8, by+g, bw, bh, "Travel Rest. [T]", self._t_tr, True)
        self.btn_v  = Button(bx, by+g*2, bw, bh, "Vaccinate 10% [V]", self._vac)
        self.btn_ns = Button(bx+bw+8, by+g*2, bw, bh, "New Strain [N]", self._ns)
        self.btn_p  = Button(bx, by+g*3, bw, bh, "Pause [SPACE]", self._t_p, True)
        self.btn_r  = Button(bx+bw+8, by+g*3, bw, bh, "Reset [R]", self.reset)
        self.btn_sr = Button(bx, by+g*4, bw, bh, "Show Radius [G]", self._t_sr, True)
        self.btn_mi = Button(bx+bw+8, by+g*4, bw, bh, "Mortality Toggle [M]", self._t_mort, True)
        self.buttons = [self.btn_sd, self.btn_q, self.btn_w, self.btn_tr,
                        self.btn_v, self.btn_ns, self.btn_p, self.btn_r,
                        self.btn_sr, self.btn_mi]

    def _t_sd(self):  self.soc_dist = not self.soc_dist; self.btn_sd.active = self.soc_dist
    def _t_q(self):   self.quarantine = not self.quarantine; self.btn_q.active = self.quarantine
    def _t_w(self):   self.waning = not self.waning; self.btn_w.active = self.waning
    def _t_tr(self):  self.travel = not self.travel; self.btn_tr.active = self.travel
    def _t_p(self):   self.paused = not self.paused; self.btn_p.active = self.paused
    def _t_sr(self):  self.show_radius = not self.show_radius; self.btn_sr.active = self.show_radius
    def _t_mort(self):
        if self.mortality > 0: self.mortality = 0.0
        else: self.mortality = MORTALITY_RATE
        self.btn_mi.active = self.mortality > 0

    def _vac(self):
        sus = [p for p in self.population if p.status == "susceptible"]
        n = max(1, int(len(sus) * VACCINATE_PCT))
        for p in random.sample(sus, min(n, len(sus))):
            p.vaccinate()

    def _ns(self):
        ns = Strain(transmissibility=0.02 + random.random() * 0.06,
                    mutation_rate=0.001 + random.random() * 0.008,
                    severity=0.5 + random.random() * 0.9)
        ns.birth_step = self.step
        self.strains.append(ns)
        sus = [p for p in self.population if p.status == "susceptible"]
        if sus:
            random.choice(sus).infect(ns)

    # --- reset ---
    def reset(self):
        Strain.reset()
        self.strains.clear()
        self.step = 0
        self.chart_hist.clear()
        self.strain_hist.clear()
        self.peak_infected = 0
        self.peak_step = 0
        self.total_ever_infected = INITIAL_INFECTED

        for _ in range(INITIAL_STRAINS):
            s = Strain(transmissibility=0.02 + random.random() * 0.03,
                       mutation_rate=0.002 + random.random() * 0.005,
                       severity=0.75 + random.random() * 0.5)
            s.birth_step = 0
            self.strains.append(s)

        self.population = [
            Person(random.randint(PERSON_RADIUS + 5, SIM_WIDTH - PERSON_RADIUS - 5),
                   random.randint(PERSON_RADIUS + 5, SIM_HEIGHT - PERSON_RADIUS - 5))
            for _ in range(POPULATION_SIZE)
        ]
        for idx in random.sample(range(POPULATION_SIZE), INITIAL_INFECTED):
            self.population[idx].infect(random.choice(self.strains))

        for b in self.buttons:
            if b.toggle:
                b.active = False
        self.soc_dist = False
        self.quarantine = False
        self.waning = False
        self.travel = False
        self.show_radius = False
        self.paused = False

    # --- simulation step ---
    def update(self):
        if self.paused:
            return
        self.step += 1

        # spatial hash
        self.sh.clear()
        for p in self.population:
            if p.alive:
                self.sh.insert(p)

        # move
        for p in self.population:
            if not p.alive:
                continue
            p.move(self.quarantine, self.speed)

            # social distancing repulsion
            if self.soc_dist and p.status != "infected":
                near = self.sh.query(p.x, p.y, SOCIAL_DIST_RADIUS)
                rx = ry = 0.0
                for o in near:
                    if o is p or not o.alive:
                        continue
                    dx = p.x - o.x
                    dy = p.y - o.y
                    d2 = dx * dx + dy * dy
                    if 0 < d2 < SOCIAL_DIST_RADIUS ** 2:
                        d = math.sqrt(d2)
                        f = SOCIAL_DIST_FORCE / d
                        rx += dx * f
                        ry += dy * f
                p.vx += rx
                p.vy += ry

            # travel restriction soft walls
            if self.travel:
                m = 45
                ft = 0.35
                if p.x < m:         p.vx += ft
                if p.x > SIM_WIDTH - m:  p.vx -= ft
                if p.y < m:         p.vy += ft
                if p.y > SIM_HEIGHT - m: p.vy -= ft

        # infection
        radius = self.inf_radius
        radius_sq = radius * radius
        new_infections = []
        for p in self.population:
            if p.status != "infected" or not p.alive or not p.strain:
                continue
            near = self.sh.query(p.x, p.y, radius)
            for o in near:
                if o.status != "susceptible" or not o.alive:
                    continue
                dx = p.x - o.x
                dy = p.y - o.y
                d2 = dx * dx + dy * dy
                if d2 < radius_sq:
                    dist = math.sqrt(d2) if d2 > 0 else 0.1
                    prob = (p.strain.transmissibility * self.global_trans
                            * (1.0 - dist / radius))
                    if random.random() < prob:
                        if (random.random() < p.strain.mutation_rate * self.global_mut
                                and len(self.strains) < MAX_STRAINS):
                            ns = p.strain.mutate(self.global_mut, self.step)
                            self.strains.append(ns)
                            new_infections.append((o, ns))
                        else:
                            new_infections.append((o, p.strain))

        for person, strain in new_infections:
            if person.status == "susceptible":
                person.infect(strain)
                self.total_ever_infected += 1

        # update statuses
        for p in self.population:
            p.update(self.mortality, self.waning)

        # record
        self._record()

    def _record(self):
        s = i = r = v = d = 0
        sc = defaultdict(int)
        for p in self.population:
            if p.status == "susceptible":  s += 1
            elif p.status == "infected":   i += 1; sc[p.strain.id] += 1 if p.strain else 0
            elif p.status == "recovered":  r += 1
            elif p.status == "vaccinated": v += 1
            elif p.status == "dead":       d += 1
        self.chart_hist.append((s, i, r, v, d))
        if len(self.chart_hist) > CHART_HISTORY_LEN:
            self.chart_hist.pop(0)
        if i > self.peak_infected:
            self.peak_infected = i
            self.peak_step = self.step
        for st in self.strains:
            sid = st.id
            self.strain_hist[sid].append(sc.get(sid, 0))
            if len(self.strain_hist[sid]) > CHART_HISTORY_LEN:
                self.strain_hist[sid].pop(0)

    def _counts(self):
        s = i = r = v = d = 0
        sc = defaultdict(int)
        for p in self.population:
            if p.status == "susceptible":  s += 1
            elif p.status == "infected":   i += 1; sc[p.strain.id] += 1 if p.strain else 0
            elif p.status == "recovered":  r += 1
            elif p.status == "vaccinated": v += 1
            elif p.status == "dead":       d += 1
        return s, i, r, v, d, sc

    # --- drawing ---
    def draw(self):
        self.screen.fill(C_BG)

        # simulation surface
        self.sim_surf.fill(C_SIM_BG)

        # travel restriction zones
        if self.travel:
            m = 45
            for rect in [(0, 0, m, SIM_HEIGHT), (SIM_WIDTH - m, 0, m, SIM_HEIGHT),
                         (0, 0, SIM_WIDTH, m), (0, SIM_HEIGHT - m, SIM_WIDTH, m)]:
                s = pygame.Surface((rect[2], rect[3]), pygame.SRCALPHA)
                s.fill((*C_TRAVEL_ZONE, 35))
                self.sim_surf.blit(s, (rect[0], rect[1]))

        # quarantine visual
        if self.quarantine:
            qs = pygame.Surface((SIM_WIDTH, SIM_HEIGHT), pygame.SRCALPHA)
            for p in self.population:
                if p.status == "infected" and p.alive:
                    pygame.draw.circle(qs, (*C_QUARANTINE_ZONE, 25),
                                       (int(p.x), int(p.y)), 20)
            self.sim_surf.blit(qs, (0, 0))

        # draw people
        for p in self.population:
            p.draw(self.sim_surf)

        # show infection radius on infected
        if self.show_radius:
            rs = pygame.Surface((SIM_WIDTH, SIM_HEIGHT), pygame.SRCALPHA)
            for p in self.population:
                if p.status == "infected" and p.alive and p.strain:
                    pygame.draw.circle(rs, (*p.strain.color, 20),
                                       (int(p.x), int(p.y)), self.inf_radius)
            self.sim_surf.blit(rs, (0, 0))

        pygame.draw.rect(self.sim_surf, C_BORDER, (0, 0, SIM_WIDTH, SIM_HEIGHT), 2)
        self.screen.blit(self.sim_surf, (0, 0))

        self._draw_chart()
        self._draw_panel()

        pygame.display.flip()

    def _draw_chart(self):
        cr = pygame.Rect(CHART_X, CHART_Y, CHART_WIDTH, CHART_HEIGHT)
        pygame.draw.rect(self.screen, C_GRAPH_BG, cr, border_radius=4)

        # grid
        for i in range(1, 4):
            y = cr.top + i * cr.height // 4
            pygame.draw.line(self.screen, C_GRID, (cr.left, y), (cr.right, y), 1)
        for i in range(1, 8):
            x = cr.left + i * cr.width // 8
            pygame.draw.line(self.screen, C_GRID, (x, cr.top), (x, cr.bottom), 1)

        pygame.draw.line(self.screen, C_TEXT, (cr.left, cr.bottom), (cr.right, cr.bottom), 2)
        pygame.draw.line(self.screen, C_TEXT, (cr.left, cr.top), (cr.left, cr.bottom), 2)

        if len(self.chart_hist) < 2:
            return

        lines = [
            ("S", C_SUSCEPTIBLE, 0),
            ("I", C_ACCENT, 1),
            ("R", C_RECOVERED, 2),
            ("V", C_VACCINATED, 3),
            ("D", C_DEAD, 4),
        ]
        n = len(self.chart_hist)
        for _, col, idx in lines:
            pts = []
            for i, rec in enumerate(self.chart_hist):
                x = cr.left + (i / CHART_HISTORY_LEN) * cr.width
                y = cr.bottom - (rec[idx] / POPULATION_SIZE) * cr.height
                pts.append((x, y))
            if len(pts) > 1:
                pygame.draw.lines(self.screen, col, False, pts, 2)

        # peak marker
        if self.peak_step > 0 and n > 0:
            px = cr.left + (min(self.peak_step, CHART_HISTORY_LEN) / CHART_HISTORY_LEN) * cr.width
            if cr.left < px < cr.right:
                pygame.draw.line(self.screen, C_ACCENT, (int(px), cr.top), (int(px), cr.bottom), 1)

        # legend
        s, i_c, r, v, d, _ = self._counts()
        lx = cr.right - 170
        items = [("Susceptible", C_SUSCEPTIBLE, s),
                 ("Infected", C_ACCENT, i_c),
                 ("Recovered", C_RECOVERED, r),
                 ("Vaccinated", C_VACCINATED, v),
                 ("Dead", C_DEAD, d)]
        for j, (nm, cl, ct) in enumerate(items):
            ly = cr.top + 6 + j * 17
            pygame.draw.rect(self.screen, cl, (lx, ly, 10, 10))
            self.screen.blit(self.font_s.render(f"{nm}: {ct}", True, C_TEXT), (lx + 14, ly - 2))

        # Y-axis labels
        for i in range(5):
            val = int(POPULATION_SIZE * (4 - i) / 4)
            y = cr.top + i * cr.height // 4
            self.screen.blit(self.font_s.render(str(val), True, C_DIM_TEXT), (cr.left - 35, y - 6))

        # title
        self.screen.blit(self.font_m.render("Epidemic Curve", True, C_TEXT), (cr.left + 5, cr.top - 20))

        # peak annotation
        peak_txt = f"Peak: {self.peak_infected} @ step {self.peak_step}"
        self.screen.blit(self.font_s.render(peak_txt, True, C_ACCENT), (cr.left + 5, cr.bottom + 3))

    def _draw_panel(self):
        pr = pygame.Rect(PANEL_X - 5, 0, PANEL_WIDTH + 10, SCREEN_HEIGHT)
        pygame.draw.rect(self.screen, C_PANEL_BG, pr)
        pygame.draw.line(self.screen, C_BORDER, (PANEL_X - 5, 0), (PANEL_X - 5, SCREEN_HEIGHT), 2)

        x = PANEL_X + 5
        y = 12

        self.screen.blit(self.font_xl.render("Virus Simulator", True, C_ACCENT), (x, y))
        y += 38
        pygame.draw.line(self.screen, C_BORDER, (x, y), (x + PANEL_WIDTH - 20, y), 1)
        y += 8

        # stats
        s, i_c, r, v, d, sc = self._counts()
        self.screen.blit(self.font_l.render(f"Step: {self.step}", True, C_TEXT), (x, y))
        y += 28

        stats = [
            (f"Susceptible:  {s}", C_SUSCEPTIBLE),
            (f"Infected:     {i_c}", C_ACCENT),
            (f"Recovered:    {r}", C_RECOVERED),
            (f"Vaccinated:   {v}", C_VACCINATED),
            (f"Dead:         {d}", C_DEAD),
        ]
        for txt, col in stats:
            self.screen.blit(self.font_m.render(txt, True, col), (x, y))
            y += 20
        y += 4
        self.screen.blit(self.font_s.render(f"Total ever infected: {self.total_ever_infected}", True, C_DIM_TEXT), (x, y))
        y += 16
        self.screen.blit(self.font_s.render(f"Peak infected: {self.peak_infected} (step {self.peak_step})", True, C_ACCENT2), (x, y))
        y += 20

        pygame.draw.line(self.screen, C_BORDER, (x, y), (x + PANEL_WIDTH - 20, y), 1)
        y += 6

        # parameters
        self.screen.blit(self.font_m.render("Parameters", True, (180, 180, 255)), (x, y))
        y += 22
        params = [
            f"Speed: {self.speed:.1f}x",
            f"Infection Radius: {self.inf_radius}",
            f"Transmissibility: {self.global_trans:.2f}",
            f"Mutation Mult: {self.global_mut:.2f}",
            f"Mortality: {self.mortality:.3f}",
            f"Strains: {len(self.strains)}/{MAX_STRAINS}",
        ]
        for t in params:
            self.screen.blit(self.font_s.render(t, True, C_DIM_TEXT), (x, y))
            y += 16
        y += 8

        pygame.draw.line(self.screen, C_BORDER, (x, y), (x + PANEL_WIDTH - 20, y), 1)
        y += 6

        # active strains detail
        self.screen.blit(self.font_m.render("Active Strains", True, C_ACCENT2), (x, y))
        y += 22

        sorted_strains = sorted(self.strains, key=lambda s: sc.get(s.id, 0), reverse=True)
        shown = 0
        for st in sorted_strains:
            cnt = sc.get(st.id, 0)
            if cnt == 0 and shown >= 6:
                continue
            pygame.draw.rect(self.screen, st.color, (x, y + 1, 10, 10))
            gen_str = f"G{st.generation}" if st.generation else "orig"
            info = f"#{st.id} T={st.transmissibility:.3f} S={st.severity:.2f} {gen_str} x{cnt}"
            self.screen.blit(self.font_s.render(info, True, C_TEXT), (x + 14, y - 1))
            y += 15
            shown += 1
            if shown >= 10:
                break

        if shown == 0:
            self.screen.blit(self.font_s.render("No active infections", True, C_DIM_TEXT), (x, y))
            y += 15

        y += 6

        # strain distribution bar
        pygame.draw.line(self.screen, C_BORDER, (x, y), (x + PANEL_WIDTH - 20, y), 1)
        y += 6
        self.screen.blit(self.font_s.render("Strain Distribution", True, (180, 180, 255)), (x, y))
        y += 18

        total_inf = max(1, sum(sc.values()))
        bw = PANEL_WIDTH - 30
        bx = x
        bh = 18
        for st in sorted_strains:
            cnt = sc.get(st.id, 0)
            if cnt == 0:
                continue
            sw = max(1, int((cnt / total_inf) * bw))
            pygame.draw.rect(self.screen, st.color, (bx, y, sw, bh))
            bx += sw
        rem = x + bw - bx
        if rem > 0:
            pygame.draw.rect(self.screen, (35, 35, 50), (bx, y, rem, bh))
        pygame.draw.rect(self.screen, C_BORDER, (x, y, bw, bh), 1)
        y += bh + 10

        # strain mini chart (last few strains by count)
        mini_y_start = y + 18
        self.screen.blit(self.font_s.render("Top Strain Curves", True, (180, 180, 255)), (x, y))
        y = mini_y_start
        mini_h = 60
        mini_w = bw
        pygame.draw.rect(self.screen, (18, 18, 30), (x, y, mini_w, mini_h), border_radius=3)
        pygame.draw.rect(self.screen, C_BORDER, (x, y, mini_w, mini_h), 1, border_radius=3)

        # plot top 4 strain histories
        top4 = sorted_strains[:4]
        max_val = 1
        for st in top4:
            hist = self.strain_hist.get(st.id, [])
            if hist:
                max_val = max(max_val, max(hist))

        for st in top4:
            hist = self.strain_hist.get(st.id, [])
            if len(hist) < 2:
                continue
            pts = []
            for i, val in enumerate(hist):
                px = x + (i / CHART_HISTORY_LEN) * mini_w
                py = y + mini_h - (val / max_val) * (mini_h - 4) - 2
                pts.append((px, py))
            if len(pts) > 1:
                pygame.draw.lines(self.screen, st.color, False, pts, 2)

        y += mini_h + 8

        # buttons
        for btn in self.buttons:
            btn.draw(self.screen, self.font_s)

        # controls help
        y = SCREEN_HEIGHT - 80
        pygame.draw.line(self.screen, C_BORDER, (x, y), (x + PANEL_WIDTH - 20, y), 1)
        y += 5
        helps = [
            "Click L=infect  R=vaccinate  |  ESC=quit",
            "Arrow keys: speed & radius",
            "+/- transmissibility  [/] mutation mult",
        ]
        for h in helps:
            self.screen.blit(self.font_s.render(h, True, C_DIM_TEXT), (x, y))
            y += 15

    # --- events ---
    def handle_events(self):
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                return False
            for btn in self.buttons:
                btn.handle(ev)

            if ev.type == pygame.KEYDOWN:
                k = ev.key
                if k == pygame.K_ESCAPE:   return False
                elif k == pygame.K_SPACE:  self._t_p()
                elif k == pygame.K_UP:     self.speed = min(5.0, self.speed + 0.5)
                elif k == pygame.K_DOWN:   self.speed = max(0.5, self.speed - 0.5)
                elif k == pygame.K_RIGHT:  self.inf_radius = min(50, self.inf_radius + 2)
                elif k == pygame.K_LEFT:   self.inf_radius = max(5, self.inf_radius - 2)
                elif k == pygame.K_v:      self._vac()
                elif k == pygame.K_s:      self._t_sd()
                elif k == pygame.K_q:      self._t_q()
                elif k == pygame.K_w:      self._t_w()
                elif k == pygame.K_t:      self._t_tr()
                elif k == pygame.K_r:      self.reset()
                elif k == pygame.K_n:      self._ns()
                elif k == pygame.K_g:      self._t_sr()
                elif k == pygame.K_m:      self._t_mort()
                elif k in (pygame.K_PLUS, pygame.K_EQUALS):
                    self.global_trans = min(3.0, self.global_trans + 0.1)
                elif k == pygame.K_MINUS:
                    self.global_trans = max(0.1, self.global_trans - 0.1)
                elif k == pygame.K_RIGHTBRACKET:
                    self.global_mut = min(5.0, self.global_mut + 0.5)
                elif k == pygame.K_LEFTBRACKET:
                    self.global_mut = max(0.0, self.global_mut - 0.5)

            if ev.type == pygame.MOUSEBUTTONDOWN:
                mx, my = ev.pos
                if 0 <= mx < SIM_WIDTH and 0 <= my < SIM_HEIGHT:
                    best = None
                    bd = 25.0
                    for p in self.population:
                        if not p.alive:
                            continue
                        d = math.hypot(p.x - mx, p.y - my)
                        if d < bd:
                            best = p
                            bd = d
                    if best:
                        if ev.button == 1 and best.status == "susceptible":
                            if self.strains:
                                best.infect(random.choice(self.strains))
                                self.total_ever_infected += 1
                        elif ev.button == 3:
                            best.vaccinate()
        return True

    # --- main loop ---
    def run(self):
        running = True
        while running:
            running = self.handle_events()
            self.update()
            self.draw()
            self.clock.tick(FPS)
        pygame.quit()
        sys.exit()


# ============================================================
if __name__ == "__main__":
    Simulation().run()