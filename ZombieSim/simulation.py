"""
Z-POC: Core simulation engine — City (SIR) + OutbreakSimulation.
Thread-safe via RLock. Features automated strategic responses.
Grid size expanded and nodes spread further apart.
"""

import random
import math
import threading

from constants import CITY_NAMES


class City:
    """A single city with SIR compartments and strategic state."""

    def __init__(self, x, y, population, name="Unknown"):
        self.x = x
        self.y = y
        self.population = population
        self.susceptible = float(population)
        self.infected = 0.0
        self.removed = 0.0
        self.name = name
        self.is_quarantined = False
        self.is_nuked = False
        self.vaccination_rate = 0.0
        self.infection_day = None
        self.connections = []
        self.daily_new = 0

    def update(self, transmission_rate, removal_rate):
        if self.infected == 0 or self.is_nuked:
            self.daily_new = 0
            return

        effective_trans = transmission_rate * (1.0 - self.vaccination_rate)
        if self.is_quarantined:
            effective_trans *= 0.3

        new_inf = min(
            (self.susceptible * self.infected / self.population) * effective_trans,
            self.susceptible,
        )
        new_rem = min(self.infected * removal_rate, self.infected)

        self.susceptible -= new_inf
        self.infected += new_inf - new_rem
        self.removed += new_rem
        self.daily_new = new_inf

    @property
    def infection_ratio(self):
        return self.infected / self.population if self.population > 0 else 0.0


class OutbreakSimulation:
    """Core simulation engine – thread-safe with RLock."""

    def __init__(self, num_cities=20, grid_size=300,
                 transmission_rate=0.3, removal_rate=0.05):
        self.grid_size = grid_size
        self.transmission_rate = transmission_rate
        self.removal_rate = removal_rate
        self.day = 0
        self.is_over = False
        self.lock = threading.RLock()
        self.events = []
        self.quarantine_active = False
        self.total_vaccinated = 0
        self.nuked_cities = 0

        # ── Automation Settings ──
        self.auto_quarantine_enabled = False
        self.auto_quarantine_threshold = 0.25
        self.auto_vaccinate_enabled = False
        self.auto_vaccinate_threshold = 0.10

        # ── build cities (with minimum distance constraint) ──
        self.cities = []
        used = random.sample(CITY_NAMES, min(num_cities, len(CITY_NAMES)))
        min_dist = 45  # Force nodes to be further apart
        
        for i in range(num_cities):
            attempts = 0
            while attempts < 100:
                x = random.randint(10, grid_size - 10)
                y = random.randint(10, grid_size - 10)
                too_close = False
                for existing_city in self.cities:
                    if math.hypot(x - existing_city.x, y - existing_city.y) < min_dist:
                        too_close = True
                        break
                if not too_close:
                    break
                attempts += 1
                
            pop = random.randint(5000, 500000)
            name = used[i] if i < len(used) else f"City-{i+1}"
            self.cities.append(City(x, y, pop, name))

        # ── road network (scaled to new grid size) ──
        connect_dist = grid_size * 0.25
        for i, c1 in enumerate(self.cities):
            for j, c2 in enumerate(self.cities):
                if i < j:
                    d = math.hypot(c1.x - c2.x, c1.y - c2.y)
                    if d < connect_dist:
                        c1.connections.append(c2)
                        c2.connections.append(c1)

        # ── patient zero ──
        p0 = random.choice(self.cities)
        with self.lock:
            p0.infected = 1
            p0.susceptible -= 1
            p0.infection_day = 0
            self.events.append(f"Day 0: Patient Zero identified in {p0.name}!")

        self.history_s = []
        self.history_i = []
        self.history_r = []
        self.history_new = []

    # ── daily tick ──────────────────────────────────────
    def step(self):
        with self.lock:
            if self.is_over:
                return
            self.day += 1

            for city in self.cities:
                city.update(self.transmission_rate, self.removal_rate)

            # ── Automated Strategic Actions ──
            if self.auto_quarantine_enabled:
                for city in self.cities:
                    if (not city.is_quarantined and not city.is_nuked and 
                        city.infection_ratio >= self.auto_quarantine_threshold):
                        self.toggle_city_quarantine(city)

            if self.auto_vaccinate_enabled:
                for city in self.cities:
                    if (not city.is_nuked and 
                        city.infection_ratio >= self.auto_vaccinate_threshold and
                        city.vaccination_rate < 0.8):
                        self.vaccinate_city(city, 0.05)

            # inter-city spread (scaled distances)
            incoming = {}
            spread_dist_primary = self.grid_size * 0.25
            spread_dist_secondary = self.grid_size * 0.15

            for src in self.cities:
                if src.infected <= 0 or src.is_quarantined or src.is_nuked:
                    continue
                for tgt in self.cities:
                    if src is tgt or tgt.susceptible <= 0 or tgt.is_nuked:
                        continue
                    if self.quarantine_active and tgt.is_quarantined:
                        continue

                    dist = math.hypot(src.x - tgt.x, src.y - tgt.y)
                    connected = tgt in src.connections

                    if connected and dist < spread_dist_primary:
                        chance = (src.infected / src.population) * 0.15
                        if not self.quarantine_active:
                            chance *= 1.5
                    elif dist < spread_dist_secondary:
                        chance = (src.infected / src.population) * 0.08
                    else:
                        continue

                    if random.random() < chance:
                        n = min(int(src.infected * 0.01), int(tgt.susceptible))
                        if n > 0:
                            incoming.setdefault(tgt, 0)
                            incoming[tgt] += n

            daily_new = 0
            for city, n in incoming.items():
                if city.infection_day is None and n > 0:
                    city.infection_day = self.day
                    self.events.append(
                        f"Day {self.day}: OUTBREAK in {city.name}! ({int(n)} cases)"
                    )
                city.infected += n
                city.susceptible -= n
                daily_new += n

            total_s = sum(c.susceptible for c in self.cities)
            total_i = sum(c.infected for c in self.cities)
            total_r = sum(c.removed for c in self.cities)

            self.history_s.append(total_s)
            self.history_i.append(total_i)
            self.history_r.append(total_r)
            self.history_new.append(daily_new)

            overrun = sum(1 for c in self.cities if c.infection_ratio > 0.5)
            infected_c = sum(1 for c in self.cities if c.infected > 0)

            if self.day == 10:
                self.events.append(
                    f"Day {self.day}: {infected_c} cities affected – situation critical."
                )
            if self.day == 30:
                self.events.append(f"Day {self.day}: Crisis enters second month.")
            if self.day % 25 == 0 and overrun > 0:
                self.events.append(
                    f"Day {self.day}: {overrun} cities overrun (>50% infected)"
                )
            if daily_new > 50000:
                self.events.append(
                    f"Day {self.day}: CATASTROPHIC SURGE – {int(daily_new):,} new infections!"
                )

            if total_i < 1:
                self.is_over = True
                self.events.append(
                    f"Day {self.day}: Outbreak ended. Total casualties: {int(total_r):,}"
                )

            if len(self.events) > 500:
                self.events = self.events[-300:]

    # ── strategic actions ───────────────────────────────
    def vaccinate_city(self, city, pct=0.1):
        with self.lock:
            if city.is_nuked:
                return
            n = int(city.susceptible * pct)
            if n > 0:
                city.susceptible -= n
                city.removed += n
                city.vaccination_rate = min(city.vaccination_rate + pct, 1.0)
                self.total_vaccinated += n
                prefix = "[AUTO] " if self.auto_vaccinate_enabled else ""
                self.events.append(
                    f"Day {self.day}: {prefix}Vaccinated {n:,} in {city.name} ({pct*100:.0f}%)"
                )

    def toggle_city_quarantine(self, city):
        with self.lock:
            if city.is_nuked:
                return
            city.is_quarantined = not city.is_quarantined
            tag = "QUARANTINED" if city.is_quarantined else "released from quarantine"
            prefix = "[AUTO] " if self.auto_quarantine_enabled else ""
            self.events.append(f"Day {self.day}: {prefix}{city.name} {tag}")

    def nuke_city(self, city):
        with self.lock:
            if city.is_nuked:
                return
            lost = int(city.susceptible + city.infected)
            city.susceptible = 0
            city.infected = 0
            city.removed = city.population
            city.is_nuked = True
            city.is_quarantined = False
            self.nuked_cities += 1
            self.events.append(
                f"Day {self.day}: ☢ {city.name} NUKED! {lost:,} lives lost."
            )

    @property
    def effective_r0(self):
        total_pop = sum(c.population for c in self.cities)
        total_s = sum(c.susceptible for c in self.cities)
        if total_pop > 0 and self.removal_rate > 0:
            return (self.transmission_rate / self.removal_rate) * (total_s / total_pop)
        return 0.0