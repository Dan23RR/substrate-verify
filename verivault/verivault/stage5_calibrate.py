"""
verivault.stage5_calibrate — output CALIBRATO a 3 vie (il differenziatore di affidabilita-prodotto).

{VULN+PoC | SAFE+certificato-immunita | ABSTAIN+banda-conforme}. Nessun prior-art emette un ABSTAIN
calibrato con banda-conforme su metrica continua (vedi docs/MOAT.md). Mai un finto-verdetto.

Conformal prediction: split-conformal su uno score continuo -> garanzia di copertura empirica >= 1-eps.
TODO(Daniel): cablare una lib matura (MAPIE / crepes / torchcp) calibrata su un set di calibrazione
held-out. Qui: una soglia conforme split-conformal minimale (sufficiente per il death-gate).
"""
from __future__ import annotations
from .schemas import Claim, Verdict, Certificate, Status


def conformal_threshold(cal_scores_safe: list[float], eps: float = 0.05) -> float:
    """Soglia tale che, con copertura 1-eps, uno score sopra-soglia NON e' un SAFE (FP controllati).
    Split-conformal minimale: quantile (1-eps) degli score dei SAFE di calibrazione."""
    if not cal_scores_safe:
        return 1.0
    s = sorted(cal_scores_safe)
    import math
    k = min(len(s) - 1, math.ceil((len(s) + 1) * (1 - eps)) - 1)
    return s[max(0, k)]


def calibrate(claim: Claim, risk: float, analyzable: bool, gate: Verdict | None,
              threshold: float) -> Certificate:
    """Combina scorer continuo (Stadio 2) + gate eseguibile (Stadio 4) in un output a 3 vie calibrato."""
    if not analyzable:
        v = Verdict(Status.ABSTAIN, confidence=risk,
                    reason="contratto non analizzabile (proxy/impl assente) -> astensione onesta")
        return Certificate(claim, v)

    # se il gate eseguibile ha disposto, ha la PRIORITA (e' la prova; lo scorer e' solo il pre-filtro)
    if gate is not None and gate.status in (Status.PASS, Status.REFUTED):
        return Certificate(claim, gate)

    # altrimenti decidi sullo scorer continuo + soglia conforme
    if risk > threshold:
        # FP=0 (review): l'estrattore STRUTTURALE deterministico (o l'euristica) PROPONE un rischio, NON DISPONE un VULN
        # senza exec-gate. Senza gate, un PASS=VULN sarebbe un falso-VULN su un vault difeso letto male -> ABSTAIN.
        if str(claim.payload.get("_source", "")).startswith("deterministic"):
            v = Verdict(Status.ABSTAIN, confidence=risk,
                        reason=f"risk {risk:.3f} PROPOSTO dall'estrattore strutturale (no exec-gate, no LLM) -> ABSTAIN "
                               "(struttura-only propone, non dispone un VULN; serve il gate per disporre)")
        else:
            v = Verdict(Status.PASS, confidence=risk,
                        reason=f"risk {risk:.3f} > soglia-conforme {threshold:.3f} (sopra la banda dei SAFE)")
    else:
        v = Verdict(Status.ABSTAIN, confidence=risk,
                    reason=f"risk {risk:.3f} entro la banda-conforme dei SAFE -> astensione (no exec-gate)")
    return Certificate(claim, v)
