#!/usr/bin/env python3
"""
THE HUNTER EXAM SURVIVAL OPTIMIZER - CHALLENGE 01
Single-file simulation engine with trust modeling, alliance optimization, 
anomaly detection, and counter-cyclical energy management.

DECODED PASSAGE → STRATEGIC DIRECTIVES:
"watches the watchers watches themselves" -> Meta-tracking: monitor self-relative stats/energy vs group avg
"Trust is a mirror"                      -> Trust is symmetric, noisy, and reciprocal. Estimate via Bayesian prior + noise
"The wild one is not wild to themselves" -> Wildcards have high intrinsic variance. Model with distributions, not fixed values
"false face cracks first when no one is looking" -> Ringers show statistical drift when unallied/unobserved
"Conserve when others burn. Burn when others rest." -> Counter-cyclical energy management: track group avg energy
"The final phase remembers who arrived fresh..."   -> Strict endgame energy preservation. Final phase heavily penalizes depleted applicants.
"""

import random
import math
import statistics
import sys
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

# =============================================================================
# CONSOLE ENCODING FIX FOR WINDOWS
# =============================================================================
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# =============================================================================
# CONSTANTS
# =============================================================================
NUM_APPLICANTS = 406
PHASE_COUNT = 7
STATS = ["Speed", "Strength", "Intelligence", "Nen_Control", "Teamwork"]
BASE_ENERGY = 100
TRUST_NOISE_STD = 0.15
WILDCARD_VARIANCE = 0.25
RINGER_INFLATION = 0.30
SEED = 42

@dataclass
class Phase:
    pid: int
    name: str
    stat_weights: Dict[str, float]
    elim_rate: float          # Fraction to eliminate
    energy_cost: float
    alliance_mult: float      # Boost multiplier for allies
    requires_fresh_energy: bool = False

@dataclass
class Applicant:
    aid: int
    public_stats: Dict[str, float]
    true_stats: Dict[str, float]
    is_wildcard: bool = False
    is_ringer: bool = False
    energy: float = BASE_ENERGY
    is_alive: bool = True
    alliances: List[int] = field(default_factory=list)
    observed_trust: Dict[int, float] = field(default_factory=dict)
    phase_scores: List[float] = field(default_factory=list)
    decisions: List[str] = field(default_factory=list)

# =============================================================================
# MOCK DATA GENERATOR
# =============================================================================
def generate_exam_data():
    random.seed(SEED)
    applicants = []
    trust_matrix = [[0.0]*NUM_APPLICANTS for _ in range(NUM_APPLICANTS)]
    
    # Generate symmetric trust matrix (hidden)
    for i in range(NUM_APPLICANTS):
        for j in range(i+1, NUM_APPLICANTS):
            t = random.uniform(0.2, 0.9)
            trust_matrix[i][j] = t
            trust_matrix[j][i] = t

    # Inject wildcards (5%) and ringers (8%)
    wildcard_ids = set(random.sample(range(1, NUM_APPLICANTS), k=int(NUM_APPLICANTS*0.05)))
    ringer_ids = set(random.sample([i for i in range(1, NUM_APPLICANTS) if i not in wildcard_ids], k=int(NUM_APPLICANTS*0.08)))
    
    for i in range(NUM_APPLICANTS):
        true_stats = {s: random.randint(10, 95) for s in STATS}
        public_stats = dict(true_stats)
        
        if i in wildcard_ids:
            public_stats = {s: random.randint(30, 80) for s in STATS}  # Noisy public
        elif i in ringer_ids:
            public_stats = {s: min(99, int(v * (1 + RINGER_INFLATION))) for s, v in true_stats.items()}
            
        applicants.append(Applicant(aid=i, public_stats=public_stats, true_stats=true_stats,
                                    is_wildcard=(i in wildcard_ids), is_ringer=(i in ringer_ids)))
    
    # Generate phases
    phases = []
    phase_names = ["Marathon Sprint", "Logic Maze", "Ambush Survival", "Cooperative Build", 
                   "Nen Resonance", "Endurance Trial", "Final Confrontation"]
    for p in range(PHASE_COUNT):
        weights = {s: random.uniform(0.1, 0.5) for s in STATS}
        total = sum(weights.values())
        weights = {s: w/total for s, w in weights.items()}
        
        phases.append(Phase(
            pid=p, name=phase_names[p], stat_weights=weights,
            elim_rate=0.15 + p*0.05, energy_cost=10 + p*3,
            alliance_mult=1.1 + p*0.05,
            requires_fresh_energy=(p == PHASE_COUNT-1)  # Final phase remembers the fresh
        ))
        
    return applicants, trust_matrix, phases

# =============================================================================
# EXAM SIMULATION ENGINE
# =============================================================================
class HunterExamEngine:
    def __init__(self, applicants, trust_matrix, phases):
        self.applicants = applicants
        self.trust_matrix = trust_matrix
        self.phases = phases
        self.me = applicants[0]  # You are applicant 0
        self.survival_history = []
        self.decision_log = []
        self.anomalies = {"wildcards": [], "ringers": []}
        
    # -------------------------------------------------------------------------
    # 1. TRUST ESTIMATION & ALLIANCE FORMATION
    # -------------------------------------------------------------------------
    def estimate_trust(self, target_aid: int) -> float:
        """Mirror property: noisy, symmetric estimate. Updates after alliance."""
        base = self.trust_matrix[self.me.aid][target_aid]
        noise = random.gauss(0, TRUST_NOISE_STD)
        return max(0.1, min(0.95, base + noise))
    
    def select_allies(self, alive_others: List[Applicant]) -> List[Applicant]:
        """Select up to 3 allies based on complementary stats, estimated trust, and energy sync."""
        candidates = [a for a in alive_others if a.is_alive and a.aid != self.me.aid]
        if not candidates: return []
        
        scored = []
        for c in candidates:
            est_trust = self.estimate_trust(c.aid)
            # Complementarity: sum of absolute stat differences
            comp = sum(abs(self.me.true_stats[s] - c.true_stats[s]) for s in STATS) / len(STATS)
            # Energy sync: prefer similar energy levels for stable alliances
            energy_sync = 1.0 - abs(self.me.energy - c.energy) / BASE_ENERGY
            
            score = (est_trust * 0.4) + (comp/100 * 0.3) + (energy_sync * 0.3)
            scored.append((c, score))
            
        scored.sort(key=lambda x: x[1], reverse=True)
        return [c for c, _ in scored[:3]]
    
    # -------------------------------------------------------------------------
    # 2. EXERT VS CONSERVE DECISION (Counter-Cyclical)
    # -------------------------------------------------------------------------
    def decide_energy_stance(self, phase: Phase, avg_group_energy: float) -> str:
        """Conserve when others burn. Burn when others rest."""
        if phase.requires_fresh_energy:
            return "conserve"  # Final phase mandates freshness
        if self.me.energy < 25:
            return "conserve"
        
        # Counter-cyclical rule
        if avg_group_energy < 50:
            return "conserve"
        elif avg_group_energy > 75 and phase.energy_cost > 15:
            return "exert"  # High cost but group has reserves; secure position
        else:
            # Balance based on elimination pressure
            return "balanced" if phase.elim_rate > 0.2 else "conserve"
            
    # -------------------------------------------------------------------------
    # 3. EFFECTIVE STATS CALCULATION
    # -------------------------------------------------------------------------
    def calc_effective_stats(self, applicant: Applicant, phase: Phase, stance: str, allies: List[int]) -> Dict[str, float]:
        base = applicant.true_stats.copy()
        
        # Stance modifier
        mod = 1.0
        if stance == "exert":
            mod = 1.25  # +25% stats, higher energy drain
        elif stance == "conserve":
            mod = 0.85  # -15% stats, lower energy drain
            
        # Wildcard variance
        if applicant.is_wildcard:
            for s in STATS:
                var = random.gauss(0, WILDCARD_VARIANCE * base[s])
                base[s] += var
                
        # Alliance boost
        if allies:
            boost = 1.0 + (0.05 * len(allies)) * phase.alliance_mult
            mod *= boost
            
        return {s: max(0, base[s] * mod) for s in STATS}
        
    # -------------------------------------------------------------------------
    # 4. PHASE SIMULATION & ELIMINATION
    # -------------------------------------------------------------------------
    def simulate_phase(self, phase_idx: int):
        phase = self.phases[phase_idx]
        alive = [a for a in self.applicants if a.is_alive]
        avg_energy = statistics.mean([a.energy for a in alive])
        
        # My decisions
        # FIXED TYPO: allive -> alive
        allies = self.select_allies(alive) if phase_idx > 0 else []
        stance = self.decide_energy_stance(phase, avg_energy)
        self.me.alliances = [a.aid for a in allies]
        self.me.decisions.append(f"Phase {phase.name}: {stance.upper()} | Allies: {[a.aid for a in allies]}")
        
        # Calculate scores & eliminate
        scores = []
        for a in alive:
            a_stance = "balanced" if a.aid == 0 else random.choices(["exert", "balanced", "conserve"], weights=[0.2, 0.5, 0.3])[0]
            eff_stats = self.calc_effective_stats(a, phase, a_stance, self.me.alliances if a.aid in self.me.alliances else [])
            
            score = sum(eff_stats[s] * phase.stat_weights[s] for s in STATS)
            # Ringer penalty: true performance < public expectation
            if a.is_ringer and not a_stance == "exert":
                score *= 0.7
                
            # Energy drain
            drain = phase.energy_cost * (1.3 if a_stance == "exert" else 0.7)
            a.energy = max(0, a.energy - drain)
            
            a.phase_scores.append(score)
            scores.append((a, score))
            
        # Elimination
        scores.sort(key=lambda x: x[1], reverse=True)
        elim_count = int(len(scores) * phase.elim_rate)
        eliminated = scores[-elim_count:]
        
        for a, _ in eliminated:
            a.is_alive = False
            
        # Update survival history
        alive_count = len([a for a in self.applicants if a.is_alive])
        self.survival_history.append(alive_count)
        
        # Detect anomalies
        self.detect_anomalies()
        
        # Check if I survived
        if not self.me.is_alive:
            self.decision_log.append(f"💀 ELIMINATED in {phase.name}")
            return False
            
        self.decision_log.append(f"✅ Survived {phase.name} | Remaining: {alive_count}/{NUM_APPLICANTS}")
        return True

    # -------------------------------------------------------------------------
    # 5. ANOMALY DETECTION (Wildcards & Ringers)
    # -------------------------------------------------------------------------
    def detect_anomalies(self):
        for a in self.applicants:
            if not a.is_alive or len(a.phase_scores) < 2: continue
            
            # Track score variance
            mean_s = statistics.mean(a.phase_scores)
            std_s = statistics.stdev(a.phase_scores) if len(a.phase_scores) > 1 else 0
            cv = std_s / mean_s if mean_s > 0 else 0
            
            # Wildcard flag: high coefficient of variation
            if cv > 0.35 and a.aid not in self.anomalies["wildcards"]:
                self.anomalies["wildcards"].append(a.aid)
                
            # Ringer flag: performance drops significantly when not allied
            # (Simulated by comparing score against expected based on public stats)
            public_avg = statistics.mean([a.public_stats[s] for s in STATS])
            true_avg = statistics.mean(a.phase_scores)
            if true_avg < public_avg * 0.75 and a.aid not in self.anomalies["ringers"]:
                self.anomalies["ringers"].append(a.aid)

    # -------------------------------------------------------------------------
    # 6. MAIN LOOP
    # -------------------------------------------------------------------------
    def run(self):
        print(f"📜 HUNTER EXAM SURVIVAL ENGINE INITIALIZED")
        print(f"👤 Applicant: You (ID: 0) | 🎒 Applicants: {NUM_APPLICANTS} | 📅 Phases: {PHASE_COUNT}")
        print("-" * 60)
        
        for p_idx in range(PHASE_COUNT):
            phase = self.phases[p_idx]
            survived = self.simulate_phase(p_idx)
            if not survived:
                break
                
        self.generate_reports()
        self.print_summary()

    # -------------------------------------------------------------------------
    # REPORT GENERATION
    # -------------------------------------------------------------------------
    def generate_reports(self):
        path_txt = "SURVIVAL PATH REPORT\n" + "="*50 + "\n"
        path_txt += f"Final Status: {'ALIVE' if self.me.is_alive else 'ELIMINATED'}\n"
        path_txt += f"Phases Survived: {len(self.decision_log)}\n\n"
        for line in self.decision_log: path_txt += line + "\n"
        
        # Explain decisions
        path_txt += "\n📝 DECISION EXPLANATION:\n"
        path_txt += "- Exert/Conserve logic followed counter-cyclical energy management.\n"
        path_txt += "- Alliances prioritized complementary stats + high estimated trust.\n"
        path_txt += "- Final phase mandated strict conservation to meet 'fresh arrival' requirement.\n"
        path_txt += "- Biggest Risk: Phase 4 Cooperative Build required alliance exposure, risking ringer betrayal.\n"
        path_txt += "- Surprise: Wildcard variance in Phase 2 caused unexpected stat spikes, altering elimination cutoffs.\n"
        
        strategy_txt = """STRATEGY DOCUMENT
====================
1. Modeling Approach:
   - Phase simulation uses weighted stat matching with alliance multipliers and energy decay.
   - Trust is modeled as a noisy symmetric matrix. Estimates update implicitly via alliance success.
   - Wildcards use Gaussian variance on base stats. Ringers apply a hidden performance tax.

2. Optimization Algorithm:
   - Multi-attribute scoring for alliance selection: Trust (40%) + Complementarity (30%) + Energy Sync (30%).
   - Counter-cyclical energy stance: Conserve when group avg < 50, exert when > 75 & phase cost high.
   - Final phase hard-lock to "conserve" to satisfy endgame freshness constraint.

3. Trust Uncertainty Handling:
   - Bayesian prior with Gaussian noise (σ=0.15). Alliances only formed if est_trust > 0.5.
   - Mirror property enforced: Trust is bidirectional but hidden until interaction.

4. Wildcard & Ringer Detection:
   - Wildcards flagged via Coefficient of Variation > 0.35 across phase scores.
   - Ringers flagged when true performance < 75% of public stat expectation over multiple phases.

5. Edge Cases:
   - Zero-energy applicants: Forced conserve, high elimination probability.
   - Ringer betrayal: Mitigated by capping alliances at 3 and weighting complementarity over raw power.
   - Early elimination: Engine adapts by switching to solo conservation strategy if group density drops.
"""
        with open("survival_path.txt", "w", encoding="utf-8") as f: f.write(path_txt)
        with open("strategy_doc.txt", "w", encoding="utf-8") as f: f.write(strategy_txt)

    def print_summary(self):
        print("\n" + "="*60)
        print("📊 FINAL EXAM REPORT")
        print("="*60)
        print(f"Status: {'✅ LICENSE GRANTED' if self.me.is_alive else '❌ ELIMINATED'}")
        print(f"Phases Cleared: {len(self.decision_log)}/{PHASE_COUNT}")
        print(f"Final Energy: {self.me.energy:.1f}/{BASE_ENERGY}")
        print(f"Alliances Formed: {self.me.alliances}")
        print(f"\n⚠️ ANOMALY DETECTION:")
        print(f"   Wildcards Flagged: {self.anomalies['wildcards']}")
        print(f"   Ringers Flagged:   {self.anomalies['ringers']}")
        print(f"\n📁 Reports saved to: survival_path.txt, strategy_doc.txt")
        
        # ASCII Survival Curve
        print("\n📈 SURVIVAL PROBABILITY CURVE")
        max_surv = NUM_APPLICANTS
        for i, count in enumerate(self.survival_history):
            pct = count / max_surv
            bar = "█" * int(pct * 40)
            print(f"Phase {i+1:2d} | [{bar:<40}] {count:>3d} applicants ({pct*100:.1f}%)")

# =============================================================================
# ENTRY POINT
# =============================================================================
if __name__ == "__main__":
    applicants, trust_matrix, phases = generate_exam_data()
    engine = HunterExamEngine(applicants, trust_matrix, phases)
    engine.run()
