"""substrate_core.domains.replay — ESECUTORE che consuma un witness passato (demo del passaggio di testimone).

Riceve via claim.params['input_witness'] i parametri d'attacco trovati da UN ALTRO dominio (es. il
controesempio REFUTED di real_cream_vault: la donazione/vittima che rompono il vault) e RI-ESEGUE
deterministicamente l'exploit con quei parametri. Una ri-esecuzione deterministica di un exploit concreto
e' una PROVA (PROVEN) che l'exploit funziona davvero coi parametri passati.

Cross-dominio: dominio-A (matematica, trova il param) -> dominio-B (esecutore, lo esegue) — un solo kernel.
"""
from __future__ import annotations

import ast

from ..kernel import Claim, Verdict, Status, Domain, register, PROVEN


def _cream_attacker_profit(donation: int, victim: int) -> int:
    """La VERA matematica Compound/Cream (no offset), integer division fedele."""
    S, A = 1, 1               # attacker ha depositato 1 wei -> 1 share
    A += donation             # donazione: totalAssets sale, totalSupply no
    vs = victim * S // A       # share della vittima (troncamento Solidity)
    S += vs; A += victim
    att_redeem = 1 * A // S    # l'attaccante redime la sua share
    return att_redeem - (1 + donation)


def gate(claim: Claim) -> Verdict:
    iw = (claim.params or {}).get("input_witness") or {}
    raw = iw.get("input")
    if raw is None:
        return Verdict(Status.ABSTAIN, executed=False,
                       reason="nessun input_witness da incatenare (passaggio di testimone vuoto)")
    try:
        D, V = ast.literal_eval(str(raw))   # i parametri passati dal cert sorgente
        D, V = int(D), int(V)
    except Exception as e:  # noqa
        return Verdict(Status.ABSTAIN, executed=False, reason=f"input_witness non parsabile: {type(e).__name__}: {e}")

    profit = _cream_attacker_profit(D, V)
    if profit > 0:
        return Verdict(Status.CONFIRMED, executed=True,
                       reason=f"exploit RI-ESEGUITO coi parametri passati (D={D}, V={V}): profit={profit} > 0",
                       witness={"donation": D, "victim": V, "profit": profit,
                                "input_from": (claim.params or {}).get("input_from")},
                       reproduce=f"replay cream-attack(D={D}, V={V}) -> profit {profit}",
                       assurance=PROVEN, coverage={"method": "ri-esecuzione deterministica del witness passato"})
    return Verdict(Status.ABSTAIN, executed=True, reason=f"parametri passati non profittevoli (profit={profit})")


def claim_templates(target: str):
    return [Claim(domain="replay", target=target, kind="replay_exploit", params={})]


REPLAY = Domain(name="replay", gate=gate, claim_templates=claim_templates,
                describe="Esecutore: ri-esegue un exploit coi parametri passati via input_witness (passaggio di testimone)")
register(REPLAY)
