"""
verivault.compose — ALGEBRA DI COMPOSIZIONE DEI CERTIFICATI (il gap che nessun competitor copre).

A1/aether/PoCo emettono UN exploit alla volta. VeriVault compone CLAIM certificati in un certificato
WHOLE-TARGET, con due operatori e la regola dell'ANELLO DEBOLE:

  JOIN/conjunction  (sicurezza):  il target e SAFE iff OGNI proprieta e PASS.
      - un solo REFUTED  -> composite REFUTED  (vuln trovata; il safe-whole NON esce)
      - un solo ABSTAIN  -> composite ABSTAIN  (non certificabile il tutto; mai finto-safe)
      - tutti PASS       -> composite PASS, confidence = MIN (l'anello piu debole detta la forza)

  MEET/disjunction (vulnerabilita): il target e VULN se QUALSIASI claim-di-vuln e PASS (un exploit basta).

La composizione e la fonte del valore "verifica > genera": claim che si COMPONGONO (CLAUDE/F0 tesi).
"""
from __future__ import annotations
from typing import Iterable
from .schemas import Claim, Verdict, Status, Certificate


def join_safety(certs: list[Certificate], target: str = "") -> Certificate:
    """Conjunction: certifica la SICUREZZA del target solo se TUTTE le proprieta reggono (anello debole)."""
    props = [c.claim.kind for c in certs]
    refuted = [c for c in certs if c.verdict.status == Status.REFUTED]
    abstained = [c for c in certs if c.verdict.status == Status.ABSTAIN]
    claim = Claim(kind="contract.safety", payload={"properties": props}, oracle="compose", target=target,
                  deps=props)
    if refuted:
        v = Verdict(Status.REFUTED,
                    counterexample={"refuted_properties": [c.claim.kind for c in refuted],
                                    "witnesses": [c.verdict.counterexample for c in refuted]},
                    reason=f"JOIN: {len(refuted)}/{len(certs)} proprieta REFUTATE -> target NON sicuro")
    elif abstained:
        v = Verdict(Status.ABSTAIN,
                    confidence=min((c.verdict.confidence for c in certs), default=0.0),
                    reason=f"JOIN: {len(abstained)}/{len(certs)} proprieta non decise -> il tutto non e certificabile")
    else:
        confs = [c.verdict.confidence for c in certs]
        weakest_i = min(range(len(certs)), key=lambda i: confs[i]) if certs else None
        v = Verdict(Status.PASS,
                    confidence=min(confs, default=0.0),
                    proof={"composed_safety": True, "properties": props,
                           "weakest_link": (props[weakest_i] if weakest_i is not None else None),
                           "weakest_confidence": (confs[weakest_i] if weakest_i is not None else None)},
                    reason=f"JOIN: tutte le {len(certs)} proprieta PASS -> target SICURO (forza = anello debole)")
    return Certificate(claim, v, composed_from=props)


def meet_vulnerability(certs: list[Certificate], target: str = "") -> Certificate:
    """Disjunction: il target e VULNERABILE se QUALSIASI claim-di-vuln e PASS (un exploit eseguito basta)."""
    props = [c.claim.kind for c in certs]
    vulns = [c for c in certs if c.verdict.status == Status.PASS and (
        (c.verdict.proof or {}).get("vulnerable") or c.verdict.counterexample)]
    claim = Claim(kind="contract.vulnerable", payload={"checks": props}, oracle="compose", target=target, deps=props)
    if vulns:
        v = Verdict(Status.PASS, confidence=1.0,
                    counterexample={"vulnerable_via": [c.claim.kind for c in vulns],
                                    "witnesses": [c.verdict.counterexample for c in vulns]},
                    reason=f"MEET: {len(vulns)} exploit ESEGUITI -> target VULNERABILE")
    else:
        v = Verdict(Status.ABSTAIN, reason="MEET: nessun exploit eseguito tra i check forniti (non = sicuro)")
    return Certificate(claim, v, composed_from=props)
