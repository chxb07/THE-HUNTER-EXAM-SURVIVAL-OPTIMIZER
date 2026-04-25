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
        self.history = []
        self.wildcard = d.get("wildcard", False)
        self.ringer = d.get("ringer", False)

def score(app, phase, allies):
    s = 0
    for k, w in phase["weights"].items():
        val = app.stats[k]
        if app.wildcard:
            val *= random.uniform(0.7, 1.3)
        s += val * w
    
    if allies:
        s *= (1 + 0.1 * len(allies))
    
    return s

def simulate(applicants, phases, self_id=0):
    me = [a for a in applicants if a.id == self_id][0]
    log = []
    
    for i, phase in enumerate(phases):
        alive = [a for a in applicants if a.alive]
        
        exert = (i % 2 == 1)
        allies = random.sample(alive, min(2, len(alive)))
        
        scores = []
        for a in alive:
            a_score = score(a, phase, allies if a.id == me.id else [])
            scores.append((a, a_score))
        
        scores.sort(key=lambda x: x[1], reverse=True)
        
        cutoff = int(len(scores) * (1 - phase["elimination_rate"]))
        survivors = scores[:cutoff]
        
        for a, _ in scores[cutoff:]:
            a.alive = False
        
        energy_cost = phase["energy_cost"] * (1.5 if exert else 1)
        me.energy -= energy_cost
        
        log.append(f"Phase {i+1}: {'Exert' if exert else 'Conserve'} | Energy: {me.energy}")
        
        if me.energy <= 0 or not me.alive:
            break
    
    return me.alive, log

def monte_carlo(applicants_data, phases, runs=100):
    success = 0
    logs = []
    
    for _ in range(runs):
        applicants = [Applicant(d) for d in applicants_data]
        alive, log = simulate(applicants, phases)
        if alive:
            success += 1
            logs = log
    
    return success / runs, logs

if __name__ == "__main__":
    with open("applicants.json") as f:
        applicants_data = json.load(f)
    
    with open("phases.json") as f:
        phases = json.load(f)
    
    prob, log = monte_carlo(applicants_data, phases)
    
    print("Survival Probability:", prob)
    
    with open("survival_path.txt", "w") as f:
        for line in log:
            f.write(line + "\n")
        f.write(f"\nSurvival Probability: {prob}\n")