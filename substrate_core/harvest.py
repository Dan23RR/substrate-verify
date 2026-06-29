"""substrate_core.harvest — LIBRERIA DI ALESSANDRIA ESEGUIBILE (ingestione GATED).

Principio (Oracle/Codd applicato ai dati di training): NON si salva mai dato grezzo nel corpus. Ogni candidato
passa per verify(); entra SOLO se produce un certificato con VERITA' ESEGUIBILE (CONFIRMED o REFUTED con witness).
Un harness vacuo / un file senza verita' eseguibile -> ABSTAIN -> RIFIUTATO. Risultato: un corpus di training in
cui OGNI esempio e' garantito matematicamente dalla stessa infrastruttura -> zero allucinazione nei dati.

Ciclo guidato-dal-deficit (futuro): un ABSTAIN dell'agente -> query di scraping mirata -> verify() -> corpus.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from .kernel import Claim, verify

_EXECUTABLE_TRUTH = {"CONFIRMED", "REFUTED"}   # ABSTAIN non e' dato verificato -> non entra nel corpus


def gated_ingest(candidates: List[dict], *, key: Optional[bytes] = None, stamp: str = "") -> Tuple[List[dict], List[dict]]:
    """candidates: lista di {domain,target,kind,params}. Ritorna (corpus_accettato, scartati).
    Accettato SOLO se il certificato e' CONFIRMED/REFUTED (verita' eseguibile col suo witness ri-eseguibile)."""
    corpus, rejected = [], []
    for c in candidates:
        env = verify(Claim(c["domain"], c["target"], c.get("kind", "ingest"), c.get("params", {}) or {}),
                     key=key, stamp=stamp)
        v = env["certificate"]["verdict"]
        if v["status"] in _EXECUTABLE_TRUTH:
            corpus.append({"target": c["target"], "label": v["status"], "assurance": v["assurance"],
                           "content_hash": env["content_hash"], "cert": env})   # esempio PROOF-CARRYING
        else:
            rejected.append({"target": c["target"], "status": v["status"], "reason": (v.get("reason") or "")[:90]})
    return corpus, rejected
