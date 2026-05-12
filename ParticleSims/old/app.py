import pygame
import random
import math
import sys
from collections import deque

# ═══════════════════════════════════════════════════════════════
#  CONFIGURATION
# ═══════════════════════════════════════════════════════════════
SIM_W, SIM_H = 800, 600
PANEL_W       = 260
WIN_W, WIN_H  = SIM_W + PANEL_W, SIM_H
FPS           = 60
INIT_PER_TYPE = 25
MAX_PARTICLES = 600

FRICTION   = 0.95
MAX_SPEED  = 5.5
TRAIL_LEN  = 15
R_MAX      = 130       # interaction range (px)
FORCE_MULT = 0.45      # global force multiplier
BETA       = 0.3       # close-range repulsion zone fraction

TYPE_NAMES  = ["Red", "Green", "Blue", "Yellow"]
TYPE_COLORS = {
    "Red":    (235, 75,  75),
    "Green":  (75,  235, 110),
    "Blue":   (75,  110, 235),
    "Yellow": (235, 235, 75),
}
P_RADIUS = 3

# UI colour palette
BG       = (8,   8,  18)
PANEL_BG = (16,  16,  30)
PANEL_LN = (40,  40,  70)
TXT      = (190, 190, 210)
TXT_DIM  = (110, 110, 140)
TXT_BR   = (240, 240, 255)
ACCENT   = (255, 220,  80)
BTN_N    = (40,  40,  65)
BTN_H    = (55,  55,  85)
BTN_A    = (70,  70, 110)
GREEN_ON = (45, 110, 55)
GREEN_HV = (55, 130, 65)


# ═══════════════════════════════════════════════════════════════
#  INTERACTION MATRIX  (Particle-Life model)
# ═══════════════════════════════════════════════════════════════
def gen_interactions():
    """Random attraction/repulsion matrix between every type pair."""
    m = {}
    for a in TYPE_NAMES:
        for b in TYPE_NAMES:
            if a == b:
                m[(a, b)] = round(random.uniform(-0.5, 0.15), 2)
            else:
                m[(a, b)] = round(random.uniform(-1.0, 1.0), 2)
    return m


def force_func(d, attraction, rmax):
    """Close-range universal repulsion + medium-range type interaction."""
    rmin = BETA * rmax
    if d < rmin:
        return d / rmin - 1.0                       # repulsive ramp
    elif d < rmax:
        return attraction * (1.0 - (d - rmin) / (rmax - rmin))
    return 0.0


# ═══════════════════════════════════════════════════════════════
#  PARTICLE
# ═══════════════════════════════════════════════════════════════
class Particle:
    __slots__ = ('x', 'y', 'vx', 'vy', 'ptype', 'color', 'trail')

    def __init__(self, x, y, ptype):
        self.x, self.y = float(x), float(y)
        self.vx = random.uniform(-0.5, 0.5)
        self.vy = random.uniform(-0.5, 0.5)
        self.ptype  = ptype
        self.color  = TYPE_COLORS[ptype]
        self.trail  = deque(maxlen=TRAIL_LEN)

    def update(self, particles, interactions, mouse_force):
        self.trail.append((self.x, self.y))

        # ── inter-particle forces ──
        fx = fy = 0.0
        for o in particles:
            if o is self:
                continue
            dx, dy = o.x - self.x, o.y - self.y
            d2 = dx * dx + dy * dy
            if 0 < d2 < R_MAX * R_MAX:
                dist = math.sqrt(d2)
                f = force_func(dist,
                               interactions.get((self.ptype, o.ptype), 0),
                               R_MAX)
                fx += (dx / dist) * f
                fy += (dy / dist) * f

        self.vx += fx * FORCE_MULT
        self.vy += fy * FORCE_MULT

        # ── mouse force ──
        if mouse_force is not None:
            mx, my, mode = mouse_force
            dx, dy = mx - self.x, my - self.y
            dist = math.hypot(dx, dy)
            if 0 < dist < 200:
                s = 2.0 / max(dist * 0.08, 0.3)
                sign = 1 if mode == "attract" else -1
                self.vx += sign * (dx / dist) * s
                self.vy += sign * (dy / dist) * s

        # ── friction & speed cap ──
        self.vx *= FRICTION
        self.vy *= FRICTION
        spd = math.hypot(self.vx, self.vy)
        if spd > MAX_SPEED:
            r = MAX_SPEED / spd
            self.vx *= r
            self.vy *= r

        # ── integrate ──
        self.x += self.vx
        self.y += self.vy

        # ── bounce off walls ──
        if self.x < 0:       self.x = 0;       self.vx =  abs(self.vx) * 0.5
        elif self.x > SIM_W: self.x = SIM_W;   self.vx = -abs(self.vx) * 0.5
        if self.y < 0:       self.y = 0;       self.vy =  abs(self.vy) * 0.5
        elif self.y > SIM_H: self.y = SIM_H;   self.vy = -abs(self.vy) * 0.5


# ═══════════════════════════════════════════════════════════════
#  PRE-RENDERED GLOW SURFACES
# ═══════════════════════════════════════════════════════════════
def make_glow(color, radius=18, peak_alpha=30):
    size = radius * 2
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    cx = cy = radius
    for r in range(radius, 0, -1):
        a = int(peak_alpha * (1 - r / radius) ** 0.6)
        pygame.draw.circle(surf, (*color, a), (cx, cy), r)
    return surf


# ═══════════════════════════════════════════════════════════════
#  BUTTON
# ═══════════════════════════════════════════════════════════════
class Button:
    def __init__(self, rect, text, *, toggle=False, active=False,
                 color_key=None, group=None):
        self.rect      = pygame.Rect(rect)
        self.text      = text
        self.toggle    = toggle
        self.active    = active
        self.color_key = color_key
        self.group     = group       # radio-group: list of sibling buttons
        self.hovered   = False

    def hover(self, mpos):
        self.hovered = self.rect.collidepoint(mpos)

    def click(self, mpos):
        if not self.rect.collidepoint(mpos):
            return False
        if self.toggle:
            self.active = not self.active
        if self.group is not None:
            for b in self.group:
                b.active = (b is self)
        return True

    def draw(self, surf, font):
        if self.active:
            bg = GREEN_HV if self.hovered else GREEN_ON
        elif self.hovered:
            bg = BTN_H
        else:
            bg = BTN_N

        pygame.draw.rect(surf, bg, self.rect, border_radius=5)
        pygame.draw.rect(surf, PANEL_LN, self.rect, 1, border_radius=5)

        if self.color_key:
            c = TYPE_COLORS[self.color_key]
            sr = pygame.Rect(self.rect.x + 5, self.rect.centery - 5, 10, 10)
            pygame.draw.rect(surf, c, sr, border_radius=2)
            t = font.render(self.text, True, TXT_BR if self.active else TXT)
            surf.blit(t, (self.rect.x + 20,
                          self.rect.centery - t.get_height() // 2))
        else:
            t = font.render(self.text, True, TXT_BR if self.active else TXT)
            surf.blit(t, t.get_rect(center=self.rect.center))


# ═══════════════════════════════════════════════════════════════
#  PYGAME INIT
# ═══════════════════════════════════════════════════════════════
pygame.init()
screen = pygame.display.set_mode((WIN_W, WIN_H))
pygame.display.set_caption("✨ Particle Life Simulation")
clock = pygame.time.Clock()

font_sm = pygame.font.Font(None, 18)
font_md = pygame.font.Font(None, 21)
font_lg = pygame.font.Font(None, 26, bold=True)
font_xl = pygame.font.Font(None, 34, bold=True)

glow_cache = {name: make_glow(TYPE_COLORS[name]) for name in TYPE_NAMES}

# ─── mutable state ────────────────────────────────────────
interactions  = gen_interactions()
particles     = []
selected_type = "Red"
mouse_mode    = "spawn"
show_trails   = True
show_glow     = True
show_links    = False
paused        = False


def spawn_initial():
    particles.clear()
    for t in TYPE_NAMES:
        for _ in range(INIT_PER_TYPE):
            particles.append(Particle(
                random.uniform(20, SIM_W - 20),
                random.uniform(20, SIM_H - 20), t))

spawn_initial()

# ─── UI layout constants ──────────────────────────────────
PX  = SIM_W + 15
PW  = PANEL_W - 30
BW2 = (PW - 8) // 2

# Type selector (radio group)
type_btns = []
for i, name in enumerate(TYPE_NAMES):
    b = Button((PX + i * (PW // 4), 152, PW // 4 - 4, 28),
               name, color_key=name, group=type_btns)
    type_btns.append(b)
type_btns[0].active = True

# Mouse-mode (radio group)
mode_btns = []
for i, mode in enumerate(["Spawn", "Attract", "Repel"]):
    b = Button((PX + i * (PW // 3), 218, PW // 3 - 4, 26),
               mode, group=mode_btns)
    mode_btns.append(b)
mode_btns[0].active = True

# Display toggles
trail_btn = Button((PX,                 272, PW // 3 - 4, 26),
                   "Trails", toggle=True, active=True)
glow_btn  = Button((PX + PW // 3,      272, PW // 3 - 4, 26),
                   "Glow",   toggle=True, active=True)
link_btn  = Button((PX + 2 * PW // 3,  272, PW // 3 - 4, 26),
                   "Links",  toggle=True, active=False)

# Action buttons
rand_btn  = Button((PX,              326, BW2, 28), "Randomize")
reset_btn = Button((PX + BW2 + 8,    326, BW2, 28), "Reset")
clear_btn = Button((PX,              360, BW2, 28), "Clear")
pause_btn = Button((PX + BW2 + 8,    360, BW2, 28), "Pause", toggle=True)

ALL_BTNS = (type_btns + mode_btns +
            [trail_btn, glow_btn, link_btn,
             rand_btn, reset_btn, clear_btn, pause_btn])


# ═══════════════════════════════════════════════════════════════
#  DRAW HELPERS
# ═══════════════════════════════════════════════════════════════
def draw_sim():
    screen.set_clip(pygame.Rect(0, 0, SIM_W, SIM_H))

    # optional connection lines between attracting pairs
    if show_links and len(particles) <= 250:
        for i in range(len(particles)):
            p = particles[i]
            for j in range(i + 1, len(particles)):
                o = particles[j]
                dx, dy = o.x - p.x, o.y - p.y
                d2 = dx * dx + dy * dy
                if d2 < 4096:  # 64 px
                    val = interactions.get((p.ptype, o.ptype), 0)
                    if val > 0:
                        dist = math.sqrt(d2)
                        f = max(0.0, min(1.0, val * (1 - dist / 64)))
                        c = ((p.color[0] + o.color[0]) // 2,
                             (p.color[1] + o.color[1]) // 2,
                             (p.color[2] + o.color[2]) // 2)
                        c2 = (int(c[0] * f * 0.5),
                              int(c[1] * f * 0.5),
                              int(c[2] * f * 0.5))
                        pygame.draw.line(screen, c2,
                            (int(p.x), int(p.y)),
                            (int(o.x), int(o.y)), 1)

    for p in particles:
        # trail
        if show_trails and len(p.trail) > 1:
            pts = list(p.trail)
            n = len(pts)
            for k in range(n - 1):
                fac = (k + 1) / n * 0.4
                c = (int(p.color[0] * fac),
                     int(p.color[1] * fac),
                     int(p.color[2] * fac))
                pygame.draw.line(screen, c,
                    (int(pts[k][0]),   int(pts[k][1])),
                    (int(pts[k+1][0]), int(pts[k+1][1])), 1)

        # glow
        if show_glow:
            gs = glow_cache[p.ptype]
            screen.blit(gs, gs.get_rect(center=(int(p.x), int(p.y))))

        # dot
        pygame.draw.circle(screen, p.color, (int(p.x), int(p.y)), P_RADIUS)
        # bright centre highlight
        bright = (min(255, p.color[0] + 80),
                  min(255, p.color[1] + 80),
                  min(255, p.color[2] + 80))
        pygame.draw.circle(screen, bright, (int(p.x), int(p.y)), 1)

    screen.set_clip(None)


def draw_matrix(x0, y0):
    screen.blit(font_md.render("Interaction Matrix", True, TXT), (x0, y0 - 18))
    cell = 26
    for j, name in enumerate(TYPE_NAMES):
        pygame.draw.circle(screen, TYPE_COLORS[name],
                           (x0 + cell * (j + 1) + cell // 2, y0 + 6), 4)
    for i, name in enumerate(TYPE_NAMES):
        pygame.draw.circle(screen, TYPE_COLORS[name],
                           (x0 + 6, y0 + cell * (i + 1) + cell // 2), 4)
    for i, t1 in enumerate(TYPE_NAMES):
        for j, t2 in enumerate(TYPE_NAMES):
            val = interactions.get((t1, t2), 0)
            cx = x0 + cell * (j + 1)
            cy = y0 + cell * (i + 1)
            rect = pygame.Rect(cx, cy, cell - 2, cell - 2)
            mag = min(abs(val), 1.0)
            if val >= 0:
                c = (int(30 + 40 * mag),
                     int(50 + 160 * mag),
                     int(30 + 40 * mag))
            else:
                c = (int(50 + 160 * mag),
                     int(30 + 40 * mag),
                     int(30 + 40 * mag))
            pygame.draw.rect(screen, c, rect, border_radius=3)
            vt = font_sm.render(f"{val:+.1f}", True, (210, 210, 210))
            screen.blit(vt, vt.get_rect(center=rect.center))


def draw_panel():
    pygame.draw.rect(screen, PANEL_BG, (SIM_W, 0, PANEL_W, WIN_H))
    pygame.draw.line(screen, PANEL_LN, (SIM_W, 0), (SIM_W, WIN_H), 2)

    # title
    screen.blit(font_xl.render("Particle Life", True, ACCENT), (PX, 10))

    # stats
    screen.blit(font_md.render(
        f"FPS: {clock.get_fps():.0f}   Particles: {len(particles)}",
        True, TXT_DIM), (PX, 44))

    # per-type counts
    counts = {t: 0 for t in TYPE_NAMES}
    for p in particles:
        counts[p.ptype] += 1
    y = 68
    for name in TYPE_NAMES:
        pygame.draw.circle(screen, TYPE_COLORS[name], (PX + 8, y + 7), 5)
        screen.blit(font_sm.render(f"{name}: {counts[name]}", True, TXT),
                    (PX + 20, y))
        y += 16

    # sections
    screen.blit(font_md.render("Select Type", True, TXT), (PX, 136))
    for b in type_btns: b.draw(screen, font_sm)

    screen.blit(font_md.render("Mouse Mode", True, TXT), (PX, 202))
    for b in mode_btns: b.draw(screen, font_sm)

    screen.blit(font_md.render("Display", True, TXT), (PX, 258))
    trail_btn.draw(screen, font_sm)
    glow_btn.draw(screen, font_sm)
    link_btn.draw(screen, font_sm)

    screen.blit(font_md.render("Actions", True, TXT), (PX, 310))
    rand_btn.draw(screen, font_sm)
    reset_btn.draw(screen, font_sm)
    clear_btn.draw(screen, font_sm)
    pause_btn.draw(screen, font_sm)

    draw_matrix(PX, 410)

    # help
    y = 530
    for line in [
        "LClick: spawn / attract / repel",
        "RClick: quick repel",
        "Space:Pause  T:Trails  G:Glow  L:Links",
        "1-4:Type  R:Random  C:Clear  X:Reset",
    ]:
        screen.blit(font_sm.render(line, True, TXT_DIM), (PX, y))
        y += 15


# ═══════════════════════════════════════════════════════════════
#  MAIN LOOP
# ═══════════════════════════════════════════════════════════════
running   = True
lmb_down  = False
rmb_down  = False
spawn_acc = 0.0

while running:
    dt = clock.tick(FPS)
    mpos = pygame.mouse.get_pos()
    mouse_force = None

    for b in ALL_BTNS:
        b.hover(mpos)

    # ── events ─────────────────────────────────────────────
    for ev in pygame.event.get():
        if ev.type == pygame.QUIT:
            running = False

        elif ev.type == pygame.MOUSEBUTTONDOWN:
            if ev.button == 1:                       # LEFT CLICK
                lmb_down = True
                ui_hit = False

                for i, b in enumerate(type_btns):
                    if b.click(mpos):
                        selected_type = TYPE_NAMES[i]; ui_hit = True
                for i, b in enumerate(mode_btns):
                    if b.click(mpos):
                        mouse_mode = ["spawn", "attract", "repel"][i]
                        ui_hit = True
                if trail_btn.click(mpos):
                    show_trails = trail_btn.active; ui_hit = True
                if glow_btn.click(mpos):
                    show_glow = glow_btn.active; ui_hit = True
                if link_btn.click(mpos):
                    show_links = link_btn.active; ui_hit = True
                if rand_btn.click(mpos):
                    interactions = gen_interactions(); ui_hit = True
                if reset_btn.click(mpos):
                    interactions = gen_interactions()
                    spawn_initial(); ui_hit = True
                if clear_btn.click(mpos):
                    particles.clear(); ui_hit = True
                if pause_btn.click(mpos):
                    paused = pause_btn.active; ui_hit = True

                # initial spawn burst
                if (not ui_hit and mpos[0] < SIM_W
                        and mouse_mode == "spawn"
                        and len(particles) < MAX_PARTICLES):
                    for _ in range(5):
                        particles.append(Particle(
                            mpos[0] + random.uniform(-12, 12),
                            mpos[1] + random.uniform(-12, 12),
                            selected_type))

            elif ev.button == 3:                     # RIGHT CLICK
                rmb_down = True

        elif ev.type == pygame.MOUSEBUTTONUP:
            if ev.button == 1: lmb_down = False; spawn_acc = 0.0
            if ev.button == 3: rmb_down = False

        elif ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_SPACE:
                paused = not paused; pause_btn.active = paused
            elif ev.key == pygame.K_t:
                show_trails = not show_trails; trail_btn.active = show_trails
            elif ev.key == pygame.K_g:
                show_glow = not show_glow; glow_btn.active = show_glow
            elif ev.key == pygame.K_l:
                show_links = not show_links; link_btn.active = show_links
            elif ev.key == pygame.K_r:
                interactions = gen_interactions()
            elif ev.key == pygame.K_c:
                particles.clear()
            elif ev.key == pygame.K_x:
                interactions = gen_interactions(); spawn_initial()
            elif ev.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
                idx = ev.key - pygame.K_1
                if idx < len(TYPE_NAMES):
                    selected_type = TYPE_NAMES[idx]
                    for i, b in enumerate(type_btns):
                        b.active = (i == idx)

    # ── mouse-held actions ─────────────────────────────────
    if mpos[0] < SIM_W:
        if rmb_down:
            mouse_force = (mpos[0], mpos[1], "repel")
        elif lmb_down and mouse_mode == "attract":
            mouse_force = (mpos[0], mpos[1], "attract")
        elif lmb_down and mouse_mode == "repel":
            mouse_force = (mpos[0], mpos[1], "repel")
        elif lmb_down and mouse_mode == "spawn":
            spawn_acc += dt
            while spawn_acc > 60 and len(particles) < MAX_PARTICLES:
                spawn_acc -= 60
                particles.append(Particle(
                    mpos[0] + random.uniform(-10, 10),
                    mpos[1] + random.uniform(-10, 10),
                    selected_type))
    else:
        spawn_acc = 0.0

    # ── update ─────────────────────────────────────────────
    if not paused:
        for p in particles:
            p.update(particles, interactions, mouse_force)

    # ── draw ───────────────────────────────────────────────
    screen.fill(BG)
    draw_sim()
    draw_panel()

    # cursor indicator
    if mpos[0] < SIM_W:
        if mouse_force is not None:
            mc = ((80, 255, 120) if mouse_force[2] == "attract"
                  else (255, 80, 80))
            pygame.draw.circle(screen, mc, mpos, 20, 1)
            pygame.draw.circle(screen, mc, mpos, 5, 1)
        elif mouse_mode == "spawn":
            pygame.draw.circle(screen, TYPE_COLORS[selected_type],
                               mpos, 14, 1)

    pygame.display.flip()

pygame.quit()
sys.exit()