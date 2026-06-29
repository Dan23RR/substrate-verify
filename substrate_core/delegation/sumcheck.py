# -*- coding: utf-8 -*-
"""sumcheck.py — DELEGA VERIFICABILE: un verificatore TINY e DEBOLE verifica #SAT (un conteggio #P) interagendo
con un prover POTENTE ma NON FIDATO, con soundness INFORMAZIONE-TEORICA (IP, Lund-Fortnow-Karloff-Nisan; IP=PSPACE).

Il punto, che sfugge ai due trap che hanno ucciso ogni altro candidato-paradigma:
  - TRAP-LEAN: il verificatore tiny NON possiede la regione (e' debole: O(n*m) field-ops, NON enumera mai 2^n).
    Un solver/enumeratore sotto lo STESSO budget esplode. La verifica nasce dalla DELEGA al prover non fidato.
  - TRAP-REWARD: la soundness viene dal PROTOCOLLO (sfide random + identita' polinomiali, Schwartz-Zippel),
    NON da un punteggio imparato. Un prover che mente sul conteggio e' beccato con prob >= 1 - (deg/p).

Il verificatore (il TCB) fa SOLO: (1) sommare due valori e confrontare; (2) scegliere una sfida random;
(3) interpolare un polinomio univariato da pochi punti; (4) UNA valutazione dell'aritmetizzazione in un punto.
Niente solver, niente enumerazione, niente fiducia nel prover. ~80 righe auditabili.
"""
from __future__ import annotations

import random as _random
from typing import Callable, Dict, List, Optional, Tuple

P = (1 << 61) - 1            # primo di Mersenne: campo F_p, soundness error ~ deg/p (trascurabile)
Clause = Tuple[int, int, int]


# --------------------------------------------------------------------------- aritmetizzazione (cheap, 1 valutazione)
def _litval(lit: int, x: Dict[int, int]) -> int:
    v = x[abs(lit)]
    return v if lit > 0 else (1 - v) % P


def eval_formula(clauses: List[Clause], x: Dict[int, int]) -> int:
    """P(x) = prod_c [ 1 - prod_{l in c} (1 - val(l)) ]  (mod p). Su input booleano = 1 sse x soddisfa tutto.
    Questa e' l'UNICA cosa 'pesante' che il verificatore fa, e la fa UNA SOLA volta, su un punto."""
    out = 1
    for c in clauses:
        prod = 1
        for l in c:
            prod = (prod * ((1 - _litval(l, x)) % P)) % P
        out = (out * ((1 - prod) % P)) % P
    return out


def var_degrees(clauses: List[Clause], n: int) -> Dict[int, int]:
    """grado di P nella variabile i = numero di clausole che la contengono (ogni clausola: grado 1 in quella var)."""
    deg = {i: 0 for i in range(1, n + 1)}
    for c in clauses:
        for v in set(abs(l) for l in c):
            deg[v] += 1
    return deg


# --------------------------------------------------------------------------- interpolazione (il verificatore)
def _lagrange_eval(points: List[Tuple[int, int]], r: int) -> int:
    """Valuta in r il polinomio univariato che passa per (xi, yi). Modular Lagrange. Tiny."""
    total = 0
    for j, (xj, yj) in enumerate(points):
        num, den = yj % P, 1
        for k, (xk, _) in enumerate(points):
            if k == j:
                continue
            num = (num * ((r - xk) % P)) % P
            den = (den * ((xj - xk) % P)) % P
        total = (total + num * pow(den, -1, P)) % P
    return total


# --------------------------------------------------------------------------- IL VERIFICATORE TINY (sound, debole)
def verify_sumcheck(clauses: List[Clause], n: int, claimed_sum: int,
                    prover, seed: int) -> Tuple[bool, str]:
    """Verifica 'sum_{x in {0,1}^n} P(x) == claimed_sum' interagendo col prover NON FIDATO.
    Ritorna (accept, reason). Soundness: se claimed_sum e' falso, accept con prob <= sum(deg)/p (trascurabile)."""
    rng = _random.Random(seed)
    deg = var_degrees(clauses, n)
    expected = claimed_sum % P
    challenges: Dict[int, int] = {}
    for i in range(1, n + 1):
        d = max(1, deg[i])
        # il prover invia g_i come valutazioni nei punti 0..d (d+1 valori) — NON fidato
        g_pts = prover.message(i, dict(challenges), d)
        if not isinstance(g_pts, list) or len(g_pts) != d + 1:
            return False, f"round {i}: messaggio malformato (attesi {d+1} valori)"
        g_pts = [(t, v % P) for t, v in zip(range(d + 1), g_pts)]
        g0 = g_pts[0][1]
        g1 = _lagrange_eval(g_pts, 1)
        # CHECK CARDINALE: g_i(0) + g_i(1) deve uguagliare il valore atteso del round precedente
        if (g0 + g1) % P != expected:
            return False, f"round {i}: g(0)+g(1) != atteso  (prover incoerente -> RIGETTO)"
        r_i = rng.randrange(P)              # SFIDA RANDOM (da cui la soundness)
        challenges[i] = r_i
        expected = _lagrange_eval(g_pts, r_i)   # riduci al punto sfidato
    # CHECK FINALE: una sola valutazione dell'aritmetizzazione nel punto random completo
    final = eval_formula(clauses, challenges)
    if final != expected:
        return False, "check finale: P(r) != g_n(r_n) (prover ha mentito su un sotto-conteggio -> RIGETTO)"
    return True, "accept: sum-check coerente in ogni round + valutazione finale (soundness ~ deg/p)"


# --------------------------------------------------------------------------- PROVER ONESTO (potente, #P work)
class HonestProver:
    """Calcola davvero g_i sommando P sul cubo booleano delle variabili rimanenti (lavoro #P, esponenziale).
    E' il prover 'potente': fa il lavoro che il verificatore NON puo' fare."""
    name = "honest"

    def __init__(self, clauses: List[Clause], n: int):
        self.clauses, self.n = clauses, n
        self.deg = var_degrees(clauses, n)

    def true_count(self) -> int:
        s = 0
        for mask in range(1 << self.n):
            x = {i: (mask >> (i - 1)) & 1 for i in range(1, self.n + 1)}
            s = (s + eval_formula(self.clauses, x)) % P
        return s

    def message(self, i: int, challenges: Dict[int, int], d: int) -> List[int]:
        # g_i(t) = sum_{x_{i+1..n} in {0,1}} P(r_1..r_{i-1}, t, x_{i+1..n})
        rest = list(range(i + 1, self.n + 1))
        out = []
        for t in range(d + 1):
            acc = 0
            for mask in range(1 << len(rest)):
                x = dict(challenges)
                x[i] = t
                for j, v in enumerate(rest):
                    x[v] = (mask >> j) & 1
                acc = (acc + eval_formula(self.clauses, x)) % P
            out.append(acc)
        return out


# --------------------------------------------------------------------------- PROVER AVVERSARI (devono essere beccati)
class LyingCountProver(HonestProver):
    """Mente sul conteggio (claimed_sum sbagliato) ma manda i g_i ONESTI -> il check di round 1 fallisce subito,
    oppure se 'aggiusta' g_1 per far tornare la somma, il check finale lo becca. Deve essere RIGETTATO."""
    name = "lying_count"
    def message(self, i, challenges, d):
        g = super().message(i, challenges, d)
        if i == 1:
            g[0] = (g[0] + 1) % P      # falsifica g_1 per far 'tornare' una somma sbagliata di +1
        return g


class TamperProver(HonestProver):
    """Onesto tranne un coefficiente manomesso in un round centrale -> beccato al punto random (Schwartz-Zippel)."""
    name = "tamper"
    def message(self, i, challenges, d):
        g = super().message(i, challenges, d)
        if i == max(1, self.n // 2):
            g[-1] = (g[-1] + 12345) % P
        return g


class RandomProver(HonestProver):
    """Manda valori casuali (un prover che non sa fare il lavoro) -> beccato quasi sempre. Deve essere RIGETTATO."""
    name = "random_garbage"
    def __init__(self, clauses, n, seed=0):
        super().__init__(clauses, n); self._rng = _random.Random(seed)
    def message(self, i, challenges, d):
        return [self._rng.randrange(P) for _ in range(d + 1)]


__all__ = ["P", "eval_formula", "var_degrees", "verify_sumcheck",
           "HonestProver", "LyingCountProver", "TamperProver", "RandomProver"]
