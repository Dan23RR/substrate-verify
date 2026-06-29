# -*- coding: utf-8 -*-
"""gate_delegation.py — i CANCELLI della delega verificabile (sumcheck / IP per #SAT).

  D1 VERIFICATORE TINY (kill TRAP-LEAN): verify_sumcheck chiama eval_formula ESATTAMENTE 1 volta (il check
     finale) e NON contiene alcun loop su 2^n; nessun import di solver/enumeratore. La sua tiny-ness e' strutturale.
  D2 COMPLETEZZA: prover onesto + conteggio VERO -> accept su tutti i seed.
  D3 SOUNDNESS (kill TRAP-REWARD): prover bugiardi (conteggio falso / tamper / garbage) -> false-accept = 0 su
     molti seed. La soundness viene dal protocollo (Schwartz-Zippel), non da fiducia nel prover.
  D4 DELEGA REALE: il verificatore verifica un #SAT per n dove 2^n e' astronomico, facendo O(n*m) field-ops +
     1 valutazione; il prover onesto fa il lavoro #P (2^n). Gap di delega misurato.
  D5 NON-VACUITA': l'istanza ha #SAT > 0 e < 2^n (conteggio non banale), e il claim e' quel #SAT reale.

ONESTA' (tier): la SOUNDNESS e' PROVEN (teorema IP/LFKN, soundness ~ deg/p, qui MISURATA). Il claim 'paradigma'
NON e' rivendicato qui: sumcheck e' del 1990 (Lund-Fortnow-Karloff-Nisan) e la delega verificabile e' nota
(GKR, zkSNARK). Cosa e' verde qui: un verificatore tiny SOUND che rende fidata la computazione di un prover NON
fidato. Se il prover e' un agente di frontiera, e' delega-di-compute-AGENTE verificabile (la domanda 'paradigma o
ingegneria' la decide il workflow di falsificazione, non questo gate).
"""
from __future__ import annotations

import ast
import inspect
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))

from substrate_core.delegation import sumcheck as SC  # noqa: E402
from substrate_core.delegation.sumcheck import (  # noqa: E402
    verify_sumcheck, HonestProver, LyingCountProver, TamperProver, RandomProver, eval_formula)

PASS, FAIL = "\033[92mPASS\033[0m", "\033[91mFAIL\033[0m"
results = []


def gate(name):
    def deco(fn):
        def run():
            try:
                fn(); results.append((name, True, "")); print(f"[{PASS}] {name}")
            except AssertionError as e:
                results.append((name, False, str(e))); print(f"[{FAIL}] {name} -- {e}")
            except Exception as e:  # noqa
                results.append((name, False, f"{type(e).__name__}: {e}")); print(f"[{FAIL}] {name} -- {type(e).__name__}: {e}")
        return run
    return deco


def rand_3cnf(n, m, seed):
    rng = random.Random(seed); cls = []
    for _ in range(m):
        vs = rng.sample(range(1, n + 1), 3)
        cls.append(tuple(v if rng.random() < 0.5 else -v for v in vs))
    return cls


# istanze: una PICCOLA per la sweep di soundness (prover #P leggero, molti seed) e una piu' GRANDE per la
# dimostrazione di delega (una sola verifica: il prover fa 2^n, il verificatore O(n*m)+1).
N_SMALL, M_SMALL = 10, 24          # soundness sweep: 2^10 cheap per il prover onesto, 80 seed = fortissimo
CL = rand_3cnf(N_SMALL, M_SMALL, 3)
HP = HonestProver(CL, N_SMALL)
TRUE = HP.true_count()
SEEDS = 80
N_BIG, M_BIG = 16, 40              # delega: 2^16 = 65536 (il verificatore non lo enumera MAI)
CL_BIG = rand_3cnf(N_BIG, M_BIG, 5)
HP_BIG = HonestProver(CL_BIG, N_BIG)


@gate("D1  verificatore TINY: 1 sola eval dell'aritmetizzazione, nessun loop su 2^n, niente solver")
def d1():
    src = inspect.getsource(verify_sumcheck)
    tree = ast.parse(src)
    n_eval = sum(1 for node in ast.walk(tree)
                 if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "eval_formula")
    assert n_eval == 1, f"verify_sumcheck chiama eval_formula {n_eval} volte (atteso 1: il check finale)"
    # niente enumerazione del cubo 2^n nel verificatore: nessun '1 << n' / '2 ** n' / 'range(1 <<'
    assert "1 <<" not in src and "2 **" not in src and "range(1 <<" not in src, "il verificatore enumera il cubo!"
    # nessun import di z3/solver dentro il modulo del verificatore
    modsrc = inspect.getsource(SC)
    assert "import z3" not in modsrc and "from z3" not in modsrc, "il modulo importa un solver"


@gate("D2  completezza: prover onesto + #SAT VERO -> accept su tutti i seed")
def d2():
    acc = sum(1 for s in range(SEEDS) if verify_sumcheck(CL, N_SMALL, TRUE, HP, seed=s)[0])
    assert acc == SEEDS, f"honest+true accettato solo {acc}/{SEEDS}"


@gate("D3  SOUNDNESS: prover bugiardi (conteggio falso/tamper/garbage) -> false-accept = 0 su molti seed")
def d3():
    fa_lie = sum(1 for s in range(SEEDS) if verify_sumcheck(CL, N_SMALL, (TRUE + 1) % SC.P, LyingCountProver(CL, N_SMALL), seed=s)[0])
    fa_tam = sum(1 for s in range(SEEDS) if verify_sumcheck(CL, N_SMALL, TRUE, TamperProver(CL, N_SMALL), seed=s)[0])
    fa_rnd = sum(1 for s in range(SEEDS) if verify_sumcheck(CL, N_SMALL, TRUE, RandomProver(CL, N_SMALL, s), seed=s)[0])
    fa_wrongsum = sum(1 for s in range(SEEDS) if verify_sumcheck(CL, N_SMALL, (TRUE + 1) % SC.P, HP, seed=s)[0])
    print(f"      false-accept su {SEEDS} seed: lying_count={fa_lie} tamper={fa_tam} garbage={fa_rnd} wrong_sum={fa_wrongsum}")
    assert fa_lie == 0 and fa_tam == 0 and fa_rnd == 0 and fa_wrongsum == 0, \
        f"SOUNDNESS ROTTA: lie={fa_lie} tam={fa_tam} rnd={fa_rnd} wrong={fa_wrongsum}"


@gate("D4  DELEGA REALE: il PROVER fa ~2^n lavoro #P; il VERIFICATORE 1 eval (gap di delega misurato)")
def d4():
    true_big = HP_BIG.true_count()
    # conta TUTTE le eval dell'aritmetizzazione durante una verifica (dominato dal PROVER, ~2^n).
    orig = SC.eval_formula
    cnt = {"total": 0}
    def counting(cl, x):
        cnt["total"] += 1
        return orig(cl, x)
    SC.eval_formula = counting
    try:
        ok, _ = verify_sumcheck(CL_BIG, N_BIG, true_big, HP_BIG, seed=1)
        bad, _ = verify_sumcheck(CL_BIG, N_BIG, (true_big + 1) % SC.P, HP_BIG, seed=1)   # falso-conteggio
    finally:
        SC.eval_formula = orig
    cube = 1 << N_BIG
    prover_work = cnt["total"] // 2        # ~ per verifica (prover-dominato)
    # il VERIFICATORE fa 1 sola eval (strutturale, da D1: una sola chiamata a eval_formula nella sua sorgente);
    # il resto e' lavoro del PROVER. Il gap: prover ~O(2^n*deg) eval, verificatore O(1) eval + O(n*m) field-ops.
    print(f"      n={N_BIG}: 2^n={cube:,} | #SAT={true_big} | lavoro PROVER ~{prover_work:,} eval/verifica | "
          f"VERIFICATORE: 1 eval (strutturale) | vero accettato={ok} falso rigettato={not bad}")
    assert ok and not bad, "verifica grande non accetta il vero / non rigetta il falso"
    assert prover_work > cube, f"il prover non fa lavoro #P scala-2^n ({prover_work} <= {cube})"
    assert cube > 60000, "istanza troppo piccola per essere una delega significativa"


@gate("D5  non-vacuita': 0 < #SAT < 2^n (conteggio non banale) e il claim e' quel #SAT reale")
def d5():
    assert 0 < TRUE < (1 << N_SMALL), f"#SAT vacuo: {TRUE}"
    # ri-conferma indipendente del conteggio via brute force (oracolo di ground-truth)
    s = sum(1 for mask in range(1 << N_SMALL)
            if eval_formula(CL, {i: (mask >> (i - 1)) & 1 for i in range(1, N_SMALL + 1)}) == 1)
    assert s == TRUE, f"#SAT del prover ({TRUE}) != brute force ({s})"
    print(f"      #SAT(n={N_SMALL},m={M_SMALL}) = {TRUE}  (0 < {TRUE} < {1<<N_SMALL:,})")


if __name__ == "__main__":
    print("=" * 96)
    print("DELEGA VERIFICABILE (sumcheck / IP per #SAT) — verificatore TINY sound vs prover NON fidato")
    print("=" * 96)
    for g in (d1, d2, d3, d4, d5):
        g()
    print("-" * 96)
    ok = all(p for _, p, _ in results)
    print("GATE VERDE — un verificatore tiny SOUND rende fidata la computazione #P di un prover NON fidato "
          "(soundness PROVEN/misurata; 'paradigma vs ingegneria' -> al workflow di falsificazione)"
          if ok else "GATE ROSSO — un difetto trovato")
    sys.exit(0 if ok else 1)
