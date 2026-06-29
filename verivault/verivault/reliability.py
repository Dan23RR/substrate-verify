"""
verivault.reliability — 2° ORACOLO, dominio NUOVO (affidabilita di sistema), STESSO kernel verification-native.

PROVA DI AGNOSTICITA (Ciclo 1-2 della notte): nessuna riga di schemas.py / algebra.py / compose.py e' riscritta.
  - Claim 'il componente i rispetta lo SLA (failure-rate <= budget)' e' disposto da un ORACOLO DETERMINISTICO
    (SlaOracle): PASS se entro budget; REFUTED + WITNESS (il pattern/eccesso di guasto) se lo viola; ABSTAIN se
    i campioni non bastano a disporre. Identica firma Oracle.decide(Claim)->Verdict del forge_gate/smt.
  - La COMPOSIZIONE di sistema riusa algebra.protocol_verdict VERBATIM: sotto coupling SUPER-ADDITIVO (guasti
    CORRELATI da una dipendenza condivisa) il weakest-link / union-bound si ROMPE e l'algebra DECLASSA ad ABSTAIN
    (mai un falso-IMMUNE) — l'analogo ESATTO del coupling-oracolo AMM (+78e21 misurato in forge), ma in un dominio
    ORTOGONALE (probabilita/affidabilita). I marginali FISSI (stessa failure-rate per-componente nei due regimi)
    sono l'auto-controllo anti-poesia: la super-additivita viene SOLO dalla correlazione, non da rischi cambiati.
"""
from __future__ import annotations
import math
from .schemas import Claim, Verdict, Status
from .oracles.base import Oracle
from .algebra import EconomicBound


class SlaOracle(Oracle):
    """Oracolo deterministico per claim 'componente entro SLA'. Dispone 3-vie come forge_gate/smt."""
    name = "sla_montecarlo"
    MIN_SAMPLES = 1000

    def decide(self, claim: Claim) -> Verdict:
        p = claim.payload
        try:
            rate = float(p["failure_rate_measured"]); sla = float(p["sla_budget"]); n = int(p.get("n_samples", 0))
        except Exception as e:  # noqa
            return Verdict(Status.ABSTAIN, reason=f"payload SLA non valido: {e}", script="reliability.SlaOracle")
        if n < self.MIN_SAMPLES:
            return Verdict(Status.ABSTAIN, reason=f"campioni insufficienti (n={n}<{self.MIN_SAMPLES}) -> non dispongo",
                           script="reliability.SlaOracle")
        if rate <= sla:
            return Verdict(Status.PASS, confidence=1.0,
                           proof={"sla_met": True, "failure_rate": rate, "budget": sla, "n_samples": n},
                           reason=f"failure-rate {rate:.5f} <= SLA {sla:.5f} -> componente entro budget",
                           script="reliability.SlaOracle")
        return Verdict(Status.REFUTED,
                       counterexample={"failure_rate": rate, "budget": sla, "excess": rate - sla,
                                       "witness_trace": p.get("witness_trace")},
                       reason=f"failure-rate {rate:.5f} > SLA {sla:.5f} -> SLA violato (witness eseguito)",
                       script="reliability.SlaOracle")


def reliability_bound(failure_rate: float, sla_budget: float, independent: bool,
                      scale: int = 10 ** 21, source: str = "") -> EconomicBound:
    """Mappa una componente su un EconomicBound del kernel (riuso, niente riscrittura):
      max_profit_wei = eccesso-su-SLA scalato  (<=0  <=>  entro budget = 'immune')
      monotone       = guasti INDIPENDENTI (nessuna dipendenza condivisa = link isolato; l'analogo agnostico del
                       fund-flow isolato DeFi). Sotto correlazione -> monotone=False -> protocol_verdict declassa.
    Il campo EconomicBound.monotone e' DOMINIO-AGNOSTICO: 'link isolato?'. La super-additivita la decide il witness misurato."""
    return EconomicBound(max_profit_wei=round((failure_rate - sla_budget) * scale),
                         range_k=1.0, monotone=bool(independent),
                         source=source or f"svc(rate={failure_rate:.4f},sla={sla_budget:.4f})")


def binom_ge_k(n: int, p: float, k: int) -> float:
    """P(>=k guasti su n) sotto INDIPENDENZA (binomiale): la predizione che il weakest-link/union-bound assume."""
    return sum(math.comb(n, j) * (p ** j) * ((1.0 - p) ** (n - j)) for j in range(k, n + 1))


def monotone_from_measured_coupling(observed_p_sys: float, predicted_independent_p_sys: float,
                                    ratio_threshold: float = 2.0) -> bool:
    """DERIVA `monotone` dal WITNESS MISURATO (NON hand-set) — chiude il crack della review C2:
    un sistema e' 'monotono' (composizione weakest-link/union-bound SOUND) SSE il guasto-di-sistema OSSERVATO non
    eccede di oltre ratio_threshold la PREDIZIONE-da-indipendenza (binom_ge_k). Se observed >> predicted -> coupling
    super-additivo MISURATO -> monotone=False -> protocol_verdict declassa ad ABSTAIN. E' l'analogo agnostico ESATTO
    di algebra.monotone_from_dependency, ma ancorato a un witness NUMERICO (come +78e21 nel DeFi), non a una proprieta
    strutturale dichiarata a mano. Cosi' la DERIVAZIONE del declass, non solo l'OPERATORE, transferisce tra domini."""
    if predicted_independent_p_sys <= 0:
        return observed_p_sys <= 0
    return observed_p_sys <= ratio_threshold * predicted_independent_p_sys
