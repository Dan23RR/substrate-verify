# -*- coding: utf-8 -*-
"""Smoke: il verificatore tiny ACCETTA il prover onesto e BECCA i bugiardi su molti seed (soundness misurata)."""
import os, sys, random
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
from substrate_core.delegation.sumcheck import (
    verify_sumcheck, HonestProver, LyingCountProver, TamperProver, RandomProver, eval_formula)


def rand_3cnf(n, m, seed):
    rng = random.Random(seed); cls = []
    for _ in range(m):
        vs = rng.sample(range(1, n + 1), 3)
        cls.append(tuple(v if rng.random() < 0.5 else -v for v in vs))
    return cls


def brute_count(clauses, n):
    s = 0
    for mask in range(1 << n):
        x = {i: (mask >> (i - 1)) & 1 for i in range(1, n + 1)}
        s += 1 if eval_formula(clauses, x) == 1 else 0
    return s


fails = []
n, m = 10, 24                  # piccolo: il prover onesto fa lavoro #P (2^n); il gate usa la sweep completa
clauses = rand_3cnf(n, m, 7)
true = brute_count(clauses, n)
print(f"istanza n={n} m={m}: #SAT (brute) = {true}")

# (1) prover ONESTO con conteggio VERO -> ACCEPT su tutti i seed
hp = HonestProver(clauses, n)
acc = sum(1 for s in range(40) if verify_sumcheck(clauses, n, true, hp, seed=s)[0])
print(f"(1) honest+true: accept {acc}/40")
if acc != 40:
    fails.append(f"(1) honest+true accettato solo {acc}/40 (atteso 40)")

# (2) prover ONESTO ma conteggio FALSO (true+1) -> RIGETTO su tutti i seed (il check di round-1 fallisce)
acc = sum(1 for s in range(40) if verify_sumcheck(clauses, n, (true + 1), hp, seed=s)[0])
print(f"(2) honest+WRONG count: accept {acc}/40 (atteso 0)")
if acc != 0:
    fails.append(f"(2) conteggio falso accettato {acc}/40")

# (3) LyingCountProver (claimed = true+1, g_1 falsificato) -> beccato w.h.p.
lp = LyingCountProver(clauses, n)
acc = sum(1 for s in range(200) if verify_sumcheck(clauses, n, (true + 1), lp, seed=s)[0])
print(f"(3) lying_count: false-accept {acc}/200 (atteso ~0)")
if acc > 1:
    fails.append(f"(3) lying_count false-accept {acc}/200 (troppo alto)")

# (4) TamperProver (claimed = true, un coeff manomesso) -> beccato al punto random w.h.p.
tp = TamperProver(clauses, n)
acc = sum(1 for s in range(200) if verify_sumcheck(clauses, n, true, tp, seed=s)[0])
print(f"(4) tamper: false-accept {acc}/200 (atteso ~0)")
if acc > 1:
    fails.append(f"(4) tamper false-accept {acc}/200")

# (5) RandomProver -> beccato quasi sempre
acc = sum(1 for s in range(200) if verify_sumcheck(clauses, n, true, RandomProver(clauses, n, s), seed=s)[0])
print(f"(5) random_garbage: false-accept {acc}/200 (atteso ~0)")
if acc > 1:
    fails.append(f"(5) random false-accept {acc}/200")

print("=" * 64)
if fails:
    print("SMOKE FALLITO:"); [print("  -", f) for f in fails]; sys.exit(1)
print("SMOKE PASS: verificatore tiny ACCETTA l'onesto-vero, RIGETTA conteggio-falso e ogni prover bugiardo")
sys.exit(0)
