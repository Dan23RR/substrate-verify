"""
verivault.numerical — 3° ORACOLO, dominio NUMERICO (stabilita di floating-point), STESSO kernel verification-native.

PROVA DI AGNOSTICITA (Ciclo 3): la meta'-ORACOLO del kernel (il disposer che porta un WITNESS ESEGUITO) transferisce a
un terzo dominio ortogonale. Un claim 'l'algoritmo A calcola la quantita' Q con errore-relativo <= eps sulla classe-input C'
e' disposto da NumericalErrorOracle cercando un WITNESS-input dove A sbaglia oltre eps vs un RIFERIMENTO ESATTO (Fraction
= razionale esatto, nessuna questione di precisione). Identica firma Oracle.decide(Claim)->Verdict del forge_gate/SlaOracle:
  PASS    : nessun witness nel budget di ricerca -> entro tolleranza
  REFUTED : trovato x* con err(x*) > eps -> witness ri-verificato in esatto (FP=0 per ri-esecuzione, come donation_witness_wei)
  ABSTAIN : nessun candidato / search vuota -> dichiarato, mai finto-verdetto
Il 'exploit' numerico = catastrophic cancellation (one-pass variance su dati a media grande). Niente dipendenze (fractions=stdlib).
"""
from __future__ import annotations
from fractions import Fraction
from .schemas import Claim, Verdict, Status
from .oracles.base import Oracle


# --- algoritmi sotto-audit (float) + riferimento ESATTO (Fraction) ---
def naive_variance_float(xs: list[float]) -> float:
    """one-pass: E[x^2] - E[x]^2. CATASTROPHIC CANCELLATION su media grande (sottrae due ~1e16 quasi-uguali)."""
    n = len(xs)
    s = sum(xs); s2 = sum(x * x for x in xs)
    return s2 / n - (s / n) ** 2

def stable_variance_float(xs: list[float]) -> float:
    """two-pass: media poi somma scarti^2. Numericamente stabile."""
    n = len(xs); m = sum(xs) / n
    return sum((x - m) ** 2 for x in xs) / n

def exact_variance(xs: list[float]) -> Fraction:
    """riferimento ESATTO via Fraction: nessuna perdita, e' il ground-truth contro cui si misura l'errore."""
    fr = [Fraction(x) for x in xs]; n = len(fr); m = sum(fr) / n
    return sum((x - m) * (x - m) for x in fr) / n

ALGOS = {
    "naive_var": (naive_variance_float, exact_variance),
    "stable_var": (stable_variance_float, exact_variance),
}


def rel_error(approx: float, exact: Fraction) -> float:
    if exact == 0:
        return abs(approx)
    return abs(Fraction(approx) - exact) / abs(exact)


class NumericalErrorOracle(Oracle):
    """Oracolo deterministico per claim 'algo entro errore-rel eps'. Dispone 3-vie come forge_gate/SlaOracle."""
    name = "numerical_error"

    def decide(self, claim: Claim) -> Verdict:
        p = claim.payload
        algo_key = p.get("algo"); eps = float(p.get("eps", 1e-6))
        candidates = p.get("candidates") or []
        if algo_key not in ALGOS:
            return Verdict(Status.ABSTAIN, reason=f"algoritmo {algo_key!r} non in registry -> non dispongo", script="numerical.NumericalErrorOracle")
        if not candidates:
            return Verdict(Status.ABSTAIN, reason="nessun input candidato (search vuota) -> non dispongo", script="numerical.NumericalErrorOracle")
        f, ref = ALGOS[algo_key]
        worst = None
        for xs in candidates:
            try:
                e = float(rel_error(f(xs), ref(xs)))
            except Exception:  # noqa
                continue
            if worst is None or e > worst[0]:
                worst = (e, xs)
            if e > eps:
                # WITNESS: ri-verifica ESATTA (FP=0): l'errore e' davvero > eps ricalcolando in Fraction
                exact = ref(xs); got = f(xs)
                return Verdict(Status.REFUTED, confidence=1.0,
                               counterexample={"witness_input": xs, "approx": got, "exact": str(exact),
                                               "rel_error": e, "eps": eps,
                                               "note": "errore ri-verificato in aritmetica esatta (Fraction)"},
                               reason=f"witness: rel_error={e:.3e} > eps={eps:.0e} su input a media grande (cancellation)",
                               script="numerical.NumericalErrorOracle")
        return Verdict(Status.PASS, confidence=1.0,
                       proof={"max_rel_error_seen": (worst[0] if worst else 0.0), "eps": eps, "n_candidates": len(candidates),
                              "scope": "entro tolleranza SUI candidati provati (non prova su tutto C)"},
                       reason=f"nessun witness > eps={eps:.0e} sui {len(candidates)} candidati -> entro tolleranza",
                       script="numerical.NumericalErrorOracle")
