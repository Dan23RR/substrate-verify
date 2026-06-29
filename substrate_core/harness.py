"""substrate_core.harness — META-VERIFICA del gate (critica #2): l'harness e' ADEGUATO?

Oggi una prop VACUA (`return True`) o un oracolo che non asserisce nulla produce comunque CONFIRMED:
il kernel e' CIECO sulla forza dell'harness. Qui ricorriamo la disciplina del kernel SULL'harness — se
l'harness non rifiuta MAI un output sbagliato, non sta verificando nulla, e il CONFIRMED va declassato a
ABSTAIN(harness-non-adeguato), col witness = il "mutante sopravvissuto" (il duale di un controesempio).

Il check di NON-VACUITA' e' progettato per NON punire le proprieta' legittime a UNA VIA (es. 'profit<=0',
'errore<tol'): quelle RIFIUTANO la regione di fallimento, quindi superano il check. Punisce solo le
proprieta' che accettano QUALSIASI output.

(La meta-verifica Solidity via slither-mutate e' la prossima fetta — qui c'e' la parte pura-Python a piu' alta leva.)
"""
from __future__ import annotations

import random
from typing import Any, List


def _corruptions(y: Any, r: random.Random) -> List[Any]:
    """Genera output CORROTTI plausibili per il tipo di y (candidati che una prop sana dovrebbe rifiutare)."""
    try:
        if isinstance(y, bool):
            return [not y]
        if isinstance(y, (int, float)):
            return [y + r.uniform(1, 1e6), y - r.uniform(1, 1e6), -y - 1.0, 0, 1e18, -1e18]
        if isinstance(y, str):
            return [y[::-1] + "X", "", y + "_CORRUPT"]
        if isinstance(y, (list, tuple)):
            yl = list(y)
            cands = [yl[::-1], yl[:-1], yl + [r.randint(-9, 9)], []]
            return [tuple(c) for c in cands] if isinstance(y, tuple) else cands
        return [None, 0, "CORRUPT", [r.randint(0, 9)]]
    except Exception:  # noqa
        return [None, 0]


def score_pyprop_harness(mod, seed: int, trials: int) -> dict:
    """Adeguatezza per NON-VACUITA': la prop rifiuta ALMENO UN output sbagliato? Se mai -> sopravvive un mutante.

    Ritorna {mutation_score, survivors, mutants_tested, method}. survivors non-vuoto => harness inadeguato.
    """
    r = random.Random(seed + 7)
    n = min(max(trials, 1), 300)
    rejected_any = False
    tested = 0
    for _ in range(n):
        try:
            x = mod.gen(r)
            y_real = mod.subject(x)
        except Exception:  # noqa
            continue
        for cand in _corruptions(y_real, r):
            tested += 1
            try:
                if not bool(mod.prop(x, cand)):
                    rejected_any = True
                    break
            except Exception:  # noqa
                pass  # un'eccezione NON e' una refutazione del mutante (inconclusivo)
        if rejected_any:
            break
    survivors = [] if rejected_any else [{
        "mutant": "vacuity",
        "note": "la prop non rifiuta MAI un output (nemmeno corrotto/casuale): potrebbe non verificare nulla",
    }]
    return {"mutation_score": 1.0 if rejected_any else 0.0,
            "survivors": survivors, "mutants_tested": tested,
            "method": "non-vacuity (corrupted-output rejection)"}
