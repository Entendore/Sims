import pygame
import sys
import random
import numpy as np
from config import *
from utils import dist, SoundManager
from world import init_world

colony, obstacles, feeding_spots, predators, ants, pheromone_map = init_world()
sound_manager = SoundManager()

# ===================== MAIN LOOP =====================
running = True
paused = False
show_food_phero = False
show_danger_phero = False
speed_mult = 1
selected_ant = None
frame_count = 0
day_length = 1800  # 30 seconds at 60fps

# Rain
is_raining = False
rain_timer = 0
rain_duration = 300
rain_drops = [(random.randint(0, GW), random.randint(0, GH)) for _ in range(150)]

def draw_text(txt, col=PANEL_TEXT, font=FONT_MD, y_pos=0):
    s = font.render(txt, True, col)
    panel_surf.blit(s, (15, y_pos))
    return y_pos + s.get_height() + 5

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            sound_manager.play("click")
            if event.key == pygame.K_SPACE: paused = not paused
            elif event.key == pygame.K_p: show_food_phero = not show_food_phero; show_danger_phero = False
            elif event.key == pygame.K_d: show_danger_phero = not show_danger_phero; show_food_phero = False
            elif event.key == pygame.K_UP: speed_mult = min(5, speed_mult + 1)
            elif event.key == pygame.K_DOWN: speed_mult = max(1, speed_mult - 1)
            elif event.key == pygame.K_r:
                colony, obstacles, feeding_spots, predators, ants, pheromone_map = init_world()
                selected_ant = None; frame_count = 0
        elif event.type == pygame.MOUSEBUTTONDOWN:
            mx, my = event.pos
            if mx < GW:
                selected_ant = None
                for a in ants:
                    if dist(a.x, a.y, mx, my) < 15:
                        selected_ant = a; break

    # Day/Night Cycle
    day_t = (frame_count % day_length) / day_length
    if day_t < 0.25: day_f = 1.0
    elif day_t < 0.5: day_f = 1.0 - (day_t - 0.25) * 4 * 0.5
    elif day_t < 0.75: day_f = 0.5
    else: day_f = 0.5 + (day_t - 0.75) * 4 * 0.5

    # Rain
    if not is_raining:
        if random.random() < 0.001:
            is_raining = True
            rain_timer = random.randint(120, rain_duration)
            rain_drops = [(random.randint(0, GW), random.randint(0, GH)) for _ in range(150)]
            sound_manager.play("rain_start")
    else:
        rain_timer -= 1
        if rain_timer <= 0: is_raining = False

    if not paused:
        for _ in range(speed_mult):
            # Evaporate & Diffuse
            pheromone_map *= (PHERO_EVAP - (0.01 if is_raining else 0.0))
            
            colony.update()
            for s in feeding_spots: s.update(day_f)

            # Ant updates
            ants_to_remove = []
            for a in ants:
                fd, ant_events = a.update(feeding_spots, colony.nx, colony.ny, pheromone_map, obstacles, predators, day_f, is_raining)
                if fd > 0: 
                    colony.deposit(fd)
                    sound_manager.play("deposit")
                for ev in ant_events:
                    if ev == "collected":
                        sound_manager.play("collect")
                if a.is_dead(): ants_to_remove.append(a)

            for a in ants_to_remove:
                ants.remove(a)
                colony.ants_lost += 1
                sound_manager.play("death")
                if a is selected_ant: selected_ant = None

            # Ant communication
            for i, a1 in enumerate(ants):
                for a2 in ants[max(0, i-5):i+5]:
                    if a1 is not a2 and dist(a1.x, a1.y, a2.x, a2.y) < 10:
                        a1.communicate(a2, feeding_spots)
                        a2.communicate(a1, feeding_spots)

            # Predators
            for p in predators:
                pred_events = p.update(ants, pheromone_map, predators)
                if "attacked" in pred_events:
                    sound_manager.play("attack")

            # Colony spawn
            if colony.can_spawn() and len(ants) < 150:
                ants.append(colony.spawn())

            frame_count += 1

    # ===================== RENDERING =====================
    # Background
    bg_g = int(180 * day_f + 40)
    bg_b = int(220 * day_f + 30)
    game_surf.fill((min(255, 140 + int(60*day_f)), min(255, bg_g), min(255, bg_b)))

    # Pheromones
    if show_food_phero or show_danger_phero:
        phero_r = np.zeros((PW, PH, 3), dtype=np.uint8)
        if show_food_phero:
            phero_r[:, :, 1] = np.clip(pheromone_map[:, :, FOOD_P].T * 20, 0, 255).astype(np.uint8)
        if show_danger_phero:
            phero_r[:, :, 0] = np.clip(pheromone_map[:, :, DANGER_P].T * 20, 0, 255).astype(np.uint8)
        ps = pygame.surfarray.make_surface(phero_r)
        scaled_p = pygame.transform.scale(ps, (GW, GH))
        scaled_p.set_alpha(150)
        game_surf.blit(scaled_p, (0, 0))

    for o in obstacles: o.draw(game_surf)
    for s in feeding_spots: s.draw(game_surf)
    colony.draw(game_surf)
    for p in predators: p.draw(game_surf)
    for a in ants: a.draw(game_surf, a is selected_ant)

    # Night overlay
    if day_f < 1.0:
        night_surf.fill((10, 10, 50, int((1 - day_f) * 150)))
        game_surf.blit(night_surf, (0, 0))

    # Rain
    if is_raining:
        for i in range(len(rain_drops)):
            rx, ry = rain_drops[i]
            pygame.draw.line(game_surf, RAIN_CLR, (rx, ry), (rx - 1, ry + 5), 1)
            rain_drops[i] = (rx - 1, ry + 8)
            if ry > GH: rain_drops[i] = (random.randint(0, GW), 0)
            if rx < 0: rain_drops[i] = (GW, rain_drops[i][1])

    screen.blit(game_surf, (0, 0))

    # ===================== PANEL =====================
    panel_surf.fill(PANEL_BG)
    y = 15

    y = draw_text("ANT COLONY SIM", PANEL_ACC, FONT_TITLE, y)
    y = draw_text("─" * 20, DARK_GRAY, FONT_MD, y)
    
    # Time / Weather
    time_str = "Day" if day_t < 0.5 else "Night"
    rain_str = " | RAIN" if is_raining else ""
    y = draw_text(f"Time: {time_str}{rain_str}", CYAN if is_raining else YELLOW, FONT_MD, y)
    y = draw_text(f"Speed: {speed_mult}x  FPS: {int(clock.get_fps())}", PANEL_TEXT, FONT_MD, y)
    y = draw_text("─" * 20, DARK_GRAY, FONT_MD, y)

    y = draw_text(f"Colony Food: {colony.food_storage:.1f}", ORANGE, FONT_MD, y)
    y = draw_text(f"Total Collected: {colony.total_collected:.1f}", GREEN, FONT_MD, y)
    y = draw_text(f"Ants: {len(ants)} | Lost: {colony.ants_lost}", WHITE, FONT_MD, y)
    y = draw_text(f"Scouts: {sum(1 for a in ants if a.ant_type==SCOUT)}", PURPLE, FONT_MD, y)
    y = draw_text(f"Workers: {sum(1 for a in ants if a.ant_type==WORKER)}", LIGHT_GRAY, FONT_MD, y)
    y = draw_text(f"Soldiers: {sum(1 for a in ants if a.ant_type==SOLDIER)}", RED, FONT_MD, y)
    y = draw_text(f"Carrying Food: {sum(1 for a in ants if a.has_food)}", ORANGE, FONT_MD, y)
    y = draw_text(f"Fleeing: {sum(1 for a in ants if a.state=='fleeing')}", YELLOW, FONT_MD, y)
    y = draw_text("─" * 20, DARK_GRAY, FONT_MD, y)

    # Legend
    y = draw_text("LEGEND", PANEL_ACC, FONT_LG, y)
    items = [
        (PURPLE, "Scout"), (BLACK, "Worker"), (RED, "Soldier"),
        (ORANGE, "Carrying Food"), (DARK_RED, "Predator"),
        (GREEN, "Foraging"), (YELLOW, "Returning"), (RED, "Fleeing")
    ]
    for c, t in items:
        pygame.draw.circle(panel_surf, c, (25, y + 8), 6)
        s = FONT_SM.render(t, True, PANEL_TEXT)
        panel_surf.blit(s, (40, y))
        y += 20

    y = draw_text("─" * 20, DARK_GRAY, FONT_MD, y)
    y = draw_text("CONTROLS", PANEL_ACC, FONT_LG, y)
    ctrls = [
        "SPACE - Pause/Resume",
        "P - Food Pheromones",
        "D - Danger Pheromones",
        "UP/DOWN - Speed",
        "R - Reset",
        "CLICK - Select Ant"
    ]
    for c in ctrls:
        y = draw_text(c, LIGHT_GRAY, FONT_SM, y)

    # Selected Ant Info
    if selected_ant:
        y = draw_text("─" * 20, DARK_GRAY, FONT_MD, y)
        y = draw_text("SELECTED ANT", CYAN, FONT_LG, y)
        a = selected_ant
        types = ["Scout", "Worker", "Soldier"]
        y = draw_text(f"Type: {types[a.ant_type]}", a.color, FONT_MD, y)
        y = draw_text(f"State: {a.state}", PANEL_TEXT, FONT_SM, y)
        y = draw_text(f"Action: {a.action}", PANEL_TEXT, FONT_SM, y)
        y = draw_text(f"Has Food: {a.has_food}", PANEL_TEXT, FONT_SM, y)
        y = draw_text(f"Age: {a.age}/{a.max_age}", PANEL_TEXT, FONT_SM, y)
        y = draw_text(f"Epsilon: {a.mdp.eps:.3f}", PANEL_TEXT, FONT_SM, y)

    screen.blit(panel_surf, (GW, 0))
    pygame.display.flip()
    clock.tick(60)

pygame.quit()
sys.exit()