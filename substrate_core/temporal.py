"""substrate_core.temporal — VERITA' A 4 DIMENSIONI (risolve il TOCTOU / decadimento della verita').

Ogni certificato su STATO EFFIMERO (on-chain, volumi, proxy) porta il suo CONTESTO DI VALIDITA':
    context = {chain_id, block, state_root}
La verita' e' ETERNA come ENUNCIATO SU QUEL BLOCCO (la ri-esecuzione @block N la riconferma per sempre), ma
NON dice nulla sul blocco successivo. Il content_hash COMMETTE al contesto (e' in claim.params, gia' hashed),
quindi un verificatore terzo legge dallo stesso oggetto firmato l'ISTANTE esatto a cui la verita' si riferisce.

RIGORE: lo stato muta -> il cert NON diventa FALSO (era vero @block N). Diventa STALE per il PRESENTE. Cio' che
scade e' l'APPLICABILITA' ad HEAD; la verita' storica resta ri-eseguibile. (Vedi CertGraph.decay per la cascata.)

Un cert SENZA context (es. un file di codice puntato dal suo hash) e' ETERNO: lo stato non lo tocca.
"""
from __future__ import annotations

from typing import Optional


def scope(env: dict) -> Optional[dict]:
    """Il contesto di validita' (chain/block/state_root) di un certificato. None = ETERNO (state-independent)."""
    return ((env.get("certificate", {}).get("claim", {}) or {}).get("params", {}) or {}).get("context")


def is_state_bound(env: dict) -> bool:
    return scope(env) is not None


def context_key(ctx: Optional[dict]):
    """Identita' dello STATO: (chain_id, state_root). Due cert sono 'sullo stesso stato' iff hanno la stessa chiave."""
    return None if ctx is None else (ctx.get("chain_id"), ctx.get("state_root"))


def compatible(a: Optional[dict], b: Optional[dict]) -> bool:
    """Componibili sull'asse temporale iff: almeno uno e' ETERNO, OPPURE stesso (chain_id, state_root)."""
    return a is None or b is None or context_key(a) == context_key(b)


def is_live(env: dict, current_state_root: Optional[str]) -> bool:
    """True se il cert riflette ancora HEAD (state_root corrente del target). Altrimenti e' STALE (storico)."""
    ctx = scope(env)
    return ctx is None or ctx.get("state_root") == current_state_root
