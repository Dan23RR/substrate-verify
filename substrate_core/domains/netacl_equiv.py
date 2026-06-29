"""substrate_core.domains.netacl_equiv — EQUIVALENZA di firewall/network-ACL (stateless) DECISA per Z3 (QF_BV).

"Due rulesets trattano OGNI pacchetto allo stesso modo? / questa refactor e' una backdoor che permette di piu'?"
Deciso per SMT (Z3, QF_BV: decidibile, sound+completo) con la STESSA forma di domains/smt.py (UNSAT-della-negazione).

  CONFIRMED@PROVEN  iff  z3 prova UNSAT( decision(A) != decision(B) )  -> nessun pacchetto li distingue (∀ pacchetto).
  REFUTED           iff  SAT -> un PACCHETTO concreto, RI-ESEGUITO da `decision_py` INDIPENDENTE (asimmetria
                         cardinale: il witness e' sound A PRESCINDERE da z3 — decision_py E' la semantica autorevole).
  ABSTAIN           fuori dal frammento (campo non dichiarato / NAT / stateful / azione ignota) -> tipato, MAI finto-proven.

Frammento DECIDIBILE: schema di campi FINITO dichiarato {name: width_bits}; ogni regola = match di RANGE [lo,hi]
unsigned su campi dichiarati + azione in {ALLOW,DENY}; first-match; default in {ALLOW,DENY}. Tutto il resto -> ABSTAIN.

SOUNDNESS: CONFIRMED e' sound RELATIVAMENTE al TCB {z3, encoder thin first-match} e allo SCHEMA DICHIARATO (non il
filo: un campo fuori schema e' invisibile -> DEVE ABSTAIN). Difesa-in-profondita': prima di firmare un CONFIRMED,
cross-check differenziale su pacchetti di CONFINE + random con decision_py; QUALSIASI disaccordo -> ABSTAIN.
Prior-art (NON e' la novita'): Header Space Analysis, Margrave, FIREMAN, AWS Zelkova. La novita' e' il LEDGER.
"""
from __future__ import annotations

import random as _random
from typing import Any, Dict, List, Optional, Tuple

from ..kernel import Claim, Verdict, Status, Domain, register, PROVEN

ALLOW, DENY = "ALLOW", "DENY"


# --------------------------------------------------------------------------- frammento (gate sintattico)
def _check_fragment(ruleset, fields: Dict[str, int]) -> Optional[str]:
    """None se il ruleset e' nel frammento; altrimenti la ragione di ABSTAIN (tipata)."""
    if not isinstance(fields, dict) or not fields or not all(isinstance(w, int) and w > 0 for w in fields.values()):
        return "schema dei campi mancante o non valido"
    if not isinstance(ruleset, list):
        return "ruleset non e' una lista di regole"
    for i, rule in enumerate(ruleset):
        if not isinstance(rule, dict) or rule.get("action") not in (ALLOW, DENY):
            return f"regola {i}: azione fuori da {{ALLOW,DENY}} (stateful/NAT/JUMP non nel frammento)"
        match = rule.get("match", {})
        if not isinstance(match, dict):
            return f"regola {i}: match malformato"
        for k, rng in match.items():
            if k not in fields:
                return f"regola {i}: campo {k!r} NON dichiarato nello schema -> fuori frammento (mai modellare-o-droppare)"
            if not (isinstance(rng, (list, tuple)) and len(rng) == 2):
                return f"regola {i}: vincolo su {k!r} non e' un range [lo,hi]"
            lo, hi = rng
            hib = (1 << fields[k]) - 1
            if not (isinstance(lo, int) and isinstance(hi, int) and 0 <= lo <= hi <= hib):
                return f"regola {i}: range [{lo},{hi}] fuori da [0,{hib}] del campo {k!r}"
    return None


# --------------------------------------------------------------------------- semantica INDIPENDENTE (pure python)
def decision_py(ruleset, default: str, packet: Dict[str, int]) -> str:
    """LA semantica autorevole del firewall: first-match. Indipendente da z3 -> rende il REFUTED sound (il
    grant/deny sul pacchetto concreto e' DECISO da questo codice, non asserito dall'oracolo)."""
    for rule in ruleset:
        ok = True
        for k, (lo, hi) in rule.get("match", {}).items():
            v = packet.get(k, 0)
            if not (lo <= v <= hi):
                ok = False
                break
        if ok:
            return rule["action"]
    return default


# --------------------------------------------------------------------------- encoding z3 (ogni predicato NELLA sua teoria)
def _decision_z3(z3, V, ruleset, default):
    """permit-predicate = nested If dall'ULTIMA regola alla prima (first-match). Range = UGE & ULE UNSIGNED
    (mai fresh-Bool su un range strutturato: e' la lezione di soundness — i range si sovrappongono)."""
    result = z3.BoolVal(default == ALLOW)
    for rule in reversed(ruleset):
        conds = [z3.And(z3.UGE(V[k], lo), z3.ULE(V[k], hi)) for k, (lo, hi) in rule.get("match", {}).items()]
        cond = z3.And(*conds) if conds else z3.BoolVal(True)
        result = z3.If(cond, z3.BoolVal(rule["action"] == ALLOW), result)
    return result


def _boundary_packets(ruleset_a, ruleset_b, fields, n_random=200, seed=12345):
    """Pacchetti di CONFINE (lo-1, lo, hi, hi+1 per ogni range usato) + random: per il cross-check differenziale."""
    rng = _random.Random(seed)
    per_field: Dict[str, set] = {k: {0, (1 << w) - 1} for k, w in fields.items()}
    for rs in (ruleset_a, ruleset_b):
        for rule in rs:
            for k, (lo, hi) in rule.get("match", {}).items():
                hib = (1 << fields[k]) - 1
                for val in (lo - 1, lo, hi, hi + 1):
                    if 0 <= val <= hib:
                        per_field[k].add(val)
    # prodotto cartesiano dei confini sarebbe esplosivo -> campiona combinando i confini per-campo
    keys = list(fields)
    pkts = []
    pools = {k: sorted(per_field[k]) for k in keys}
    for _ in range(n_random + 64):
        pkts.append({k: rng.choice(pools[k]) if rng.random() < 0.7 else rng.randint(0, (1 << fields[k]) - 1)
                     for k in keys})
    return pkts


# --------------------------------------------------------------------------- gate
def gate(claim: Claim) -> Verdict:
    try:
        import z3
    except Exception as e:  # noqa
        return Verdict(Status.ABSTAIN, executed=False, reason=f"z3 non disponibile: {type(e).__name__}")
    p = claim.params or {}
    A, B = p.get("rulesetA"), p.get("rulesetB")
    fields = p.get("fields")
    da, db = p.get("defaultA", DENY), p.get("defaultB", DENY)
    if A is None or B is None or fields is None:
        return Verdict(Status.ABSTAIN, executed=False, reason="mancano rulesetA/rulesetB/fields")
    if da not in (ALLOW, DENY) or db not in (ALLOW, DENY):
        return Verdict(Status.ABSTAIN, executed=True, reason="default fuori da {ALLOW,DENY}",
                       coverage={"out_of_fragment": True})
    for rs, nm in ((A, "A"), (B, "B")):
        bad = _check_fragment(rs, fields)
        if bad:
            return Verdict(Status.ABSTAIN, executed=True, reason=f"ruleset {nm} fuori dal frammento: {bad}",
                           coverage={"out_of_fragment": True})

    V = {k: z3.BitVec(k, w) for k, w in fields.items()}
    decA, decB = _decision_z3(z3, V, A, da), _decision_z3(z3, V, B, db)

    # NON-VACUITA': almeno un ruleset deve permettere qualche pacchetto (deny-all==deny-all non e' un PROVEN interessante).
    # BUDGET anche qui (stesso timeout della disuguaglianza): 'vacuous' e' un flag INFORMATIVO che NON gating il
    # verdetto, ma il suo solver gira per primo a ogni chiamata -> senza timeout sarebbe un ramo di hang non budgetato.
    sv = z3.Solver(); sv.set("timeout", int(max(200, min(30000, p.get("timeout_ms", 10000)))))
    sv.add(z3.Or(decA, decB))
    vacuous = (sv.check() == z3.unsat)   # z3.unknown (timeout) -> vacuous=False (non-proven-vacuo: default sicuro)

    s = z3.Solver()
    s.set("timeout", int(max(200, min(30000, p.get("timeout_ms", 10000)))))
    s.add(decA != decB)
    r = s.check()

    if r == z3.unsat:
        # DIFESA-IN-PROFONDITA': prima di firmare PROVEN, cross-check differenziale con la semantica indipendente
        for pkt in _boundary_packets(A, B, fields):
            if decision_py(A, da, pkt) != decision_py(B, db, pkt):
                return Verdict(Status.ABSTAIN, executed=True,
                               reason="z3 dice equivalenti ma decision_py DISACCORDA su un pacchetto -> infedelta' encoder: ABSTAIN",
                               coverage={"cross_check": "FAILED", "packet": pkt})
        return Verdict(Status.CONFIRMED, executed=True,
                       reason="rulesets EQUIVALENTI: nessun pacchetto li distingue (Z3 QF_BV UNSAT-della-disuguaglianza)",
                       witness={"equivalent": True, "method": "z3-qfbv", "vacuous": vacuous},
                       reproduce="z3: unsat(decision(A) != decision(B))", assurance=PROVEN,
                       coverage={"method": "QF_BV UNSAT-of-inequality", "exhaustive": True, "oracle": "z3-trusted",
                                 "header_space": fields, "vacuous": vacuous, "cross_check": "passed"},
                       assurance_caveat="PROVEN sound su QF_BV (Z3 decidibile+completo) RELATIVO allo SCHEMA di campi "
                                        "DICHIARATO e alla semantica STATELESS first-match — NON il filo; campi fuori schema -> ABSTAIN.")
    if r == z3.unknown:
        return Verdict(Status.ABSTAIN, executed=True, reason="z3 unknown (timeout) -> ABSTAIN onesto",
                       coverage={"timeout_ms": p.get("timeout_ms", 10000)})
    # SAT: decodifica il modello in un PACCHETTO concreto e RI-ESEGUI sotto decision_py (indipendente)
    m = s.model()
    pkt = {k: (m.eval(V[k], model_completion=True).as_long()) for k in fields}
    pa, pb = decision_py(A, da, pkt), decision_py(B, db, pkt)
    if pa == pb:
        return Verdict(Status.ABSTAIN, executed=True,
                       reason="z3 dice distinti ma decision_py NON distingue il pacchetto -> infedelta' encoder: ABSTAIN, non un REFUTED dubbio",
                       coverage={"packet": pkt, "reverify": "non-distinguishing"})
    direction = "B_allows_more (BACKDOOR)" if (pb == ALLOW and pa == DENY) else \
                ("A_allows_more (REGRESSION)" if (pa == ALLOW and pb == DENY) else "differ")
    return Verdict(Status.REFUTED, executed=True,
                   reason="rulesets NON equivalenti: pacchetto che li distingue, RI-ESEGUITO da decision_py (controesempio ESEGUITO)",
                   witness={"packet": pkt, "A_decision": pa, "B_decision": pb, "direction": direction, "header_space": fields},
                   reproduce="decision_py(A,pkt) != decision_py(B,pkt)", assurance=PROVEN,
                   coverage={"method": "z3 SAT model -> packet, ri-eseguito da decision_py", "oracle": "executed-counterexample"},
                   assurance_caveat="REFUTED FORTE: il pacchetto e' rieseguito dalla semantica INDIPENDENTE decision_py "
                                    "-> sound anche se l'encoding z3 fosse imperfetto (asimmetria cardinale).")


def claim_templates(target: str):
    return [Claim(domain="netacl_equiv", target=target, kind="equivalence", params={})]


NETACL_EQUIV = Domain(name="netacl_equiv", gate=gate, claim_templates=claim_templates,
                      describe="Equivalenza di firewall/ACL stateless per Z3 QF_BV: EQUIV->PROVEN | distingue->REFUTED+pacchetto eseguito | fuori-frammento->ABSTAIN")
register(NETACL_EQUIV)

__all__ = ["gate", "decision_py", "NETACL_EQUIV", "ALLOW", "DENY"]
