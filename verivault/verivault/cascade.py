"""
verivault.cascade — CASCATA DI VERIFICA TIERED, instradata per costo, sotto refute-gate unico.

  T0  scorer-deterministico (gratis)          -> pre-filtro / astensione cheap
  T1  SMT/Z3 (ms)                              -> witness D* (vuln) o CERTIFICATO-IMMUNITA-SU-CONTINUO (safe)
  T3  exec-gate forge (la prova)               -> esegue il witness -> PoC garantito-violante

ONESTA MISURATA (eval/test_smt_tier.py, 63 casi): T1 e' SOUND (witness reali, 0 exploit mancati) ma su
modelli ERC4626 standard NON aggiunge recall sul grid-9-punti (recall-gain=0). Il valore di T1 e' quindi
(a) il CERTIFICATO-IMMUNITA-SU-CONTINUO del MODELLO a forma-chiusa (qualita-prova, non 9 campioni). NOTA ONESTA:
il witness D* di T1 NON e' ancora cablato in T3 (TODO); oggi T3 forge ri-verifica indipendentemente sulla propria griglia.
T2 (fuzz medusa) e' opzionale (AGPL-subprocess, assente). Routing early-exit: paga forge solo quando serve.
"""
from __future__ import annotations
from typing import Optional
from .schemas import Claim, Verdict, Status
from .oracles.base import OracleRegistry


def run_cascade(claim: Claim, registry: OracleRegistry,
                risk: Optional[float] = None, low_threshold: float = 0.05) -> Verdict:
    """Instrada T0->T1->T3 con early-exit. Ritorna il Verdict piu forte (prova eseguita > certificato-SMT > scorer)."""
    # T0: pre-filtro scorer (se rischio bassissimo e nessun dubbio, astieni cheap senza spendere Z3/forge)
    if risk is not None and risk < low_threshold:
        return Verdict(Status.ABSTAIN, confidence=risk, reason=f"T0: risk {risk:.3f} sotto-soglia -> astensione cheap")

    # T1: SMT (ms) come SHORTCUT solo per MODELLI a forma-chiusa VALIDATI (closed_form_model=True).
    # Su CODICE REALE l'UNSAT-SMT certifica il MODELLO assunto, NON il bytecode -> NON deve short-circuitare:
    # passa sempre a T3 (forge, form-agnostico) per non SOPPRIMERE una VULN su fatti mislabelati (review).
    smt = registry._oracles.get("smt")
    if smt is not None:
        v1 = smt.decide(claim)
        if (v1.status != Status.ABSTAIN and v1.proof and v1.proof.get("immunity_certificate")
                and claim.payload.get("closed_form_model")):
            return v1                              # immunita-su-continuo del MODELLO validato: chiuso, no forge
        # (il witness D* di T1 NON e' ancora cablato in T3: T3 forge ri-verifica indipendentemente sulla griglia.)

    # T3: exec-gate forge (l'unica PROVA che fa uscire un VULN; un witness sbagliato -> forge fallisce -> ABSTAIN, FP=0)
    forge = registry._oracles.get("forge_gate")
    if forge is None:
        return Verdict(Status.ABSTAIN, reason="T3 forge_gate non registrato")
    return forge.decide(claim)
