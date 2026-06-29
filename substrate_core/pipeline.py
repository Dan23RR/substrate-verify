"""substrate_core.pipeline — PASSAGGIO DI TESTIMONE (proof-carrying dataflow).

L'output (witness) di un certificato in un dominio diventa l'INPUT cryptograficamente-legato di un claim in
un altro dominio. Il claim successivo registra `input_from` = content_hash del cert sorgente e `input_witness`
= il witness passato; il kernel RI-ESEGUE il claim. La catena di fiducia e' un DAG: se il sorgente cambia,
il successivo va invalidato (CertGraph.invalidate).

Disciplina FERREA: il DATO passa, ma il VERDETTO no. Ogni anello e' ri-eseguito dal gate del kernel -> nessuna
fiducia ereditata senza esecuzione. (E' il primitivo che, composto, costruisce ontologia, reattivita', indagini.)
"""
from __future__ import annotations

from typing import Optional

from .kernel import Claim, verify


def pipe(source_env: dict, next_claim: dict, *, key: Optional[bytes] = None, stamp: str = "") -> dict:
    """Incatena: il witness di `source_env` -> input del claim `next_claim` ({domain,target,kind,params}).
    Il claim successivo viene RI-ESEGUITO dal kernel e registra la provenienza cryptografica del suo input."""
    sv = source_env["certificate"]["verdict"]
    src_hash = source_env.get("content_hash", "")
    witness = sv.get("witness", {}) or {}
    params = dict(next_claim.get("params") or {})
    params["input_from"] = src_hash             # legame cryptografico al cert sorgente
    params["input_witness"] = witness           # il testimone passato (i dati)
    params["input_status"] = sv.get("status")   # da quale verdetto proviene (audit)
    claim = Claim(domain=str(next_claim.get("domain", "")), target=str(next_claim.get("target", "")),
                  kind=str(next_claim.get("kind", "piped")), params=params)
    return verify(claim, key=key, stamp=stamp)


def binding_verified(source_env: dict, next_env: dict) -> bool:
    """Check del LEGAME cross-dominio (R3 / Nova-IVC public-IO bind), eseguito dal kernel, NON una pretesa del prover.
    True iff il cert successivo dichiara `input_from == content_hash(source)` E `input_witness == witness(source)`.
    Una falsa provenienza fallisce qui (hash o witness disuguali) -> l'arco non e' valido."""
    p = (next_env.get("certificate", {}).get("claim", {}) or {}).get("params", {}) or {}
    src_hash = source_env.get("content_hash")
    src_witness = (source_env.get("certificate", {}).get("verdict", {}) or {}).get("witness", {}) or {}
    return bool(src_hash) and p.get("input_from") == src_hash and p.get("input_witness") == src_witness
