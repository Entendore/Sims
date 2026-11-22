# ai.py
"""
AI decision-making: MDP policy planner + MCTS hex-expansion search.
"""


class CivMDP:
    """27-state (3×3×3), 4-action deterministic MDP solved via value iteration."""
    STATES = [(s, e, m) for s in range(3) for e in range(3) for m in range(3)]
    ACTIONS = ["military", "economy", "culture", "stability"]

    @staticmethod
    def _transition(state, action):
        s, e, m = state
        if action == "military":
            ns = min(2, s + 1) if m >= 1 else s
            ne = max(0, e - 1) if m < 2 else e
            nm = min(2, m + 1)
        elif action == "economy":
            ns = s
            ne = min(2, e + 1)
            nm = max(0, m - 1) if e < 2 else m
        elif action == "culture":
            ns = min(2, s + 1) if e >= 1 else s
            ne = min(2, e + 1) if m >= 1 else e
            nm = m
        else:  # stability
            ns = min(2, s + 1)
            ne = max(0, e - 1) if s < 1 else e
            nm = m
        return (ns, ne, nm)

    @staticmethod
    def _reward(action, state, next_state):
        s, e, m = state
        ns, ne, nm = next_state
        if action == "military":
            return 5 * (nm - m) - 2 * max(0, e - ne) + 1
        elif action == "economy":
            return 8 * (ne - e) - 1 * max(0, m - nm) + 2
        elif action == "culture":
            return 4 * max(0, nm - m) + 3 * max(0, ne - e) + 1
        else:
            return 6 * max(0, ns - s) + 1

    def __init__(self, gamma=0.9, epsilon=0.01):
        self.gamma = gamma
        self.policy, self.values = self._solve(epsilon)

    def _solve(self, eps):
        V = {s: 0.0 for s in self.STATES}
        while True:
            delta = 0.0
            for s in self.STATES:
                v = V[s]
                best = -1e9
                for a in self.ACTIONS:
                    ns = self._transition(s, a)
                    r = self._reward(a, s, ns)
                    best = max(best, r + self.gamma * V[ns])
                V[s] = best
                delta = max(delta, abs(v - V[s]))
            if delta < eps:
                break
        policy = {}
        for s in self.STATES:
            policy[s] = max(
                self.ACTIONS,
                key=lambda a, s=s: self._reward(a, s, self._transition(s, a))
                + self.gamma * V[self._transition(s, a)],
            )
        return policy, V

    @staticmethod
    def civ_to_state(civ):
        s = 0 if civ.stability < 0.35 else (1 if civ.stability < 0.65 else 2)
        e = 0 if civ.economy < 0.35 else (1 if civ.economy < 0.65 else 2)
        m = 0 if civ.military < 0.35 else (1 if civ.military < 0.65 else 2)
        return (s, e, m)

    def get_action(self, civ):
        return self.policy.get(self.civ_to_state(civ), "economy")


class ExpansionMCTS:
    """Monte-Carlo Tree Search (UCB1) for hex expansion decisions."""

    def __init__(self, civ, world, terrain, resources, rivers=None, iterations=60):
        self.civ = civ
        self.world = world
        self.terrain = terrain
        self.resources = resources
        self.rivers = rivers or set()
        self.iterations = iterations

    def _candidates(self):
        cands = set()
        for h in self.civ.hexes:
            for n in hex_neighbors(*h):
                if n not in self.world and self.terrain.get(n, "plains") != "water":
                    cands.add(n)
        return list(cands)

    def _evaluate(self, h):
        from data import TERRAINS, RESOURCES
        t = self.terrain.get(h, "plains")
        score = TERRAINS[t]["growth"] * 10 + TERRAINS[t]["food"] * 5 + TERRAINS[t]["defense"] * 2
        if h in self.resources:
            score += RESOURCES[self.resources[h]]["value"] * 20
        if h in self.rivers:
            score += 8
        adj_own = sum(1 for n in hex_neighbors(*h) if n in self.civ.hexes)
        score += adj_own * 3
        for n in hex_neighbors(*h):
            if n not in self.world and n not in self.civ.hexes:
                if self.terrain.get(n, "plains") != "water":
                    score += self._eval_simple(n) * 0.1
        for n in hex_neighbors(*h):
            if n in self.world and self.world[n] != self.civ.name:
                score += 2
        return score

    def _eval_simple(self, h):
        from data import TERRAINS, RESOURCES
        t = self.terrain.get(h, "plains")
        s = TERRAINS[t]["growth"] * 5
        if h in self.resources:
            s += RESOURCES[self.resources[h]]["value"] * 10
        if h in self.rivers:
            s += 4
        return s

    def search(self):
        import random, math
        from hex_utils import hex_neighbors
        cands = self._candidates()
        if not cands:
            return None
        if len(cands) == 1:
            return cands[0]
        scores = {h: 0.0 for h in cands}
        visits = {h: 0 for h in cands}
        total = 0
        for _ in range(self.iterations):
            unvisited = [h for h in cands if visits[h] == 0]
            if unvisited:
                h = random.choice(unvisited)
            else:
                log_t = math.log(max(1, total))
                h = max(cands, key=lambda c: scores[c] / visits[c]
                        + 1.4 * math.sqrt(log_t / visits[c]))
            result = self._evaluate(h) + random.gauss(0, 2)
            scores[h] += result
            visits[h] += 1
            total += 1
        return max(cands, key=lambda h: scores[h] / max(1, visits[h]))