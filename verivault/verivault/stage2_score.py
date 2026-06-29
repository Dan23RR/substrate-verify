"""
verivault.stage2_score — SCORER DETERMINISTICO continuo (anti-Schaeffer) sui fatti tipizzati.

Porta la logica W5 MISURATA in questa ricerca (exp/w5v2_score.py): su fatti estratti dall'LLM
+ scorer deterministico di ~20 righe, AUC 0.604 (regex) -> 0.776 (tutti) -> 0.920 (analizzabili),
con astensione onesta sui contratti 'unknown' (proxy senza impl). E' lo Stadio 1+2 del protocollo.

Output: un RISCHIO CONTINUO in [0,1] (NON binario). Il binario viene solo dalla calibrazione (Stadio 5).
Regola anti-Schaeffer: se l'effetto svanisce passando dal binario al continuo -> artefatto (vedi eval/).
"""
from __future__ import annotations
from typing import Any


def defense_risk(facts: dict[str, Any]) -> tuple[float, bool]:
    """Rischio continuo di donation/first-depositor inflation dai fatti tipizzati.
    Ritorna (risk in [0,1], analyzable). analyzable=False -> il pipeline ASTIENE (non indovina).
    facts attesi: totalAssets_type, effective_offset_magnitude, dead_shares, defense_strength, donation_vector."""
    tat = facts.get("totalAssets_type")
    if tat not in ("internal_accounting", "external_balanceOf"):
        return 0.5, False                       # unknown (proxy/impl assente) -> ASTIENE

    ds = float(facts.get("defense_strength", 0.0) or 0.0)
    risk = 1.0 - ds                              # base: forza-difesa calibrata dall'LLM (Stadio 1)

    if tat == "internal_accounting":
        # accounting interno = immune a donazione diretta -> rischio molto basso (W5: questi separano puliti)
        risk *= 0.2
    elif tat == "external_balanceOf":
        off = float(facts.get("effective_offset_magnitude", 0.0) or 0.0)
        dead = bool(facts.get("dead_shares"))
        if not dead and off < 1e3:               # manipolabile + offset insufficiente -> rischio alto
            risk = max(risk, 0.85)
    return max(0.0, min(1.0, risk)), True
