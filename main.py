import json
import random
import numpy as np

random.seed(42)
np.random.seed(42)

class Applicant:
    def __init__(self, d):
        self.id = d["id"]
        self.stats = d["stats"]
        self.energy = d["energy"]
        self.alive = True
        self.wildcard = d.get("wildcard", False)

def compute_score(app, phase):
    val = 0
    for k, w in phase["weights"].items():
        stat = app.stats[k]
        if app.wildcard:
            stat *= random.uniform(0.8, 1.2)
        val += stat * w
    return val

def clone(apps):
    return [Applicant({
        "id": a.id,
        "stats": a.stats.copy(),
        "energy": a.energy,
        "wildcard": a.wildcard
    }) for a in apps]

def simulate_one_phase(apps, phase, exert, self_id=0):
    me = [a for a in apps if a.id == self_id][0]
    alive = [a for a in apps if a.alive]

    base = [(a, compute_score(a, phase)) for a in alive]
    base.sort(key=lambda x: x[1], reverse=True)

    top = [a for a, _ in base[:max(5, len(base)//10)]]
    allies = random.sample([a for a in top if a.id != me.id], k=min(2, len(top)-1)) if len(top) > 1 else []

    scores = []
    for a in alive:
        val = compute_score(a, phase)

        if a.id == me.id:
            val *= 1.15 if exert else 0.9
            val *= (1 + 0.1 * len(allies))

        scores.append((a, val))

    scores.sort(key=lambda x: x[1], reverse=True)

    cutoff = max(1, int(len(scores) * (1 - phase["elimination_rate"])))
    for a, _ in scores[cutoff:]:
        a.alive = False

    me.energy -= phase["energy_cost"] * (1.2 if exert else 0.5)

    return me.alive, me.energy

def decide(apps, phase, self_id=0):
    trials = 15
    exert_score = 0
    conserve_score = 0

    for _ in range(trials):
        a1 = clone(apps)
        alive1, e1 = simulate_one_phase(a1, phase, True, self_id)
        exert_score += (1 if alive1 else 0) + e1 * 0.02

        a2 = clone(apps)
        alive2, e2 = simulate_one_phase(a2, phase, False, self_id)
        conserve_score += (1 if alive2 else 0) + e2 * 0.02

    return exert_score > conserve_score

def simulate(applicants, phases, self_id=0):
    me = [a for a in applicants if a.id == self_id][0]
    log = []

    for i, phase in enumerate(phases):
        alive = [a for a in applicants if a.alive]
        if me not in alive:
            break

        # rank-based safety check
        base = [(a, compute_score(a, phase)) for a in alive]
        base.sort(key=lambda x: x[1], reverse=True)
        rank = [a.id for a, _ in base].index(me.id)
        danger = rank / len(base)

        if me.energy < 25:
            exert = False
        elif danger > 0.6:
            exert = True
        else:
            exert = decide(applicants, phase, self_id)

        top = [a for a, _ in base[:max(5, len(base)//10)]]
        allies = random.sample([a for a in top if a.id != me.id], k=min(2, len(top)-1)) if len(top) > 1 else []

        scores = []
        for a in alive:
            val = compute_score(a, phase)

            if a.id == me.id:
               val *= 1.15 if exert else 0.9
               val *= (1 + 0.1 * len(allies))

            scores.append((a, val))

        scores.sort(key=lambda x: x[1], reverse=True)

        cutoff = max(1, int(len(scores) * (1 - phase["elimination_rate"])))
        for a, _ in scores[cutoff:]:
            a.alive = False

        me.energy -= phase["energy_cost"] * (1.2 if exert else 0.5)

        log.append(f"Phase {i+1}: {'Exert' if exert else 'Conserve'} | Rank:{rank} | Energy:{me.energy:.1f}")

        if me.energy <= 0:
            me.alive = False
            break

    return me.alive, log

def monte_carlo(data, phases, runs=300):
    success = 0
    best_log = []

    for _ in range(runs):
        apps = [Applicant(d) for d in data]
        alive, log = simulate(apps, phases)

        if alive:
            success += 1
            best_log = log

    return success / runs, best_log

if __name__ == "__main__":
    with open("applicants.json") as f:
        data = json.load(f)

    with open("phases.json") as f:
        phases = json.load(f)

    prob, log = monte_carlo(data, phases)

    print("Survival Probability:", prob)

    with open("survival_path.txt", "w") as f:
        for line in log:
            f.write(line + "\n")
        f.write(f"\nSurvival Probability: {prob}\n")