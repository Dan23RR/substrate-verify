"""substrate_core.rlvr.oracle — il SEAM UNICO verso il verificatore (single source of truth).

Tutto il resto di rlvr/ passa di qui per parlare con l'oracolo: cosi' l'import esplicito di
`regex_equiv` (NON auto-registrato nel kernel __init__) sta in UN posto, e il path del verdetto
(`env['certificate']['verdict']`, NON `env['assurance']`) non si sbaglia mai.

VERIFICATO eseguendo (2026-06-07):
  verify_equiv('a+','aa*') -> CONFIRMED/proven, witness None
  verify_equiv('a+','a*')  -> REFUTED/proven,   witness '' (stringa VUOTA = witness REALE, non assente)
  verify_equiv('a+','b+')  -> REFUTED/proven,   witness 'b'
  verify_equiv('\\w+','\\w+') -> ABSTAIN/none   (semantica unicode non modellata)
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

# Import ESPLICITO: regex_equiv si auto-registra a import-time MA il kernel __init__ non lo importa.
from substrate_core.domains import regex_equiv  # noqa: F401  (side-effect: register("regex_equiv"))
from substrate_core import verify, Claim

# Seed di firma. Credenziali REALI solo da env OS; fallback a un seed di dev costante (NON un segreto).
_DEV_SEED = b"rlvr-dev-seed"


def signing_key() -> bytes:
    """Seed Ed25519 (bytes). Da env OS `SUBSTRATE_RLVR_KEY` se presente, altrimenti seed di dev.
    Mai una chiave in chiaro nel codice/chat: l'env-var e' il canale."""
    env = os.environ.get("SUBSTRATE_RLVR_KEY")
    return env.encode("utf-8") if env else _DEV_SEED


# Stato del witness: REFUTED puo' dare una stringa distinguente (anche ''), oppure None se il
# testimone e' oltre il budget ("REFUTED debole") o se il verdetto e' CONFIRMED/ABSTAIN.
def _extract_witness(verdict: Dict[str, Any]) -> Optional[str]:
    w = verdict.get("witness") or {}
    ds = w.get("distinguishing_string")
    # '' e' un witness valido (a* matcha '', a+ no) -> NON confonderlo con assente.
    return ds if isinstance(ds, str) else None


def estrai_verdetto(env: Dict[str, Any]) -> Dict[str, Any]:
    """Estrae i campi che contano da una busta firmata. Path corretto: env['certificate']['verdict']."""
    v = env["certificate"]["verdict"]
    return {
        "status": v["status"],                 # CONFIRMED | REFUTED | ABSTAIN
        "assurance": v["assurance"],            # proven | ... | none
        "executed": v.get("executed", False),
        "witness": _extract_witness(v),         # str (anche '') se REFUTED forte; None altrimenti
        "reason": v.get("reason", ""),
        "content_hash": env.get("content_hash"),
        "sig": env.get("sig"),
        "pubkey": env.get("pubkey"),
    }


def verify_equiv(r1: str, r2: str, *, key: Optional[bytes] = None,
                 target: str = "rlvr") -> Dict[str, Any]:
    """Adjudica l'equivalenza regex r1 vs r2 via l'oracolo sound. Ritorna il verdetto estratto +
    la busta grezza (per provenance/.scar). TOTALE: input spazzatura -> ABSTAIN, mai crash."""
    if key is None:
        key = signing_key()
    env = verify(Claim(domain="regex_equiv", target=target, kind="equivalence",
                       params={"r1": r1, "r2": r2}), key=key)
    out = estrai_verdetto(env)
    out["raw_envelope"] = env
    return out


__all__ = ["verify_equiv", "estrai_verdetto", "signing_key"]
