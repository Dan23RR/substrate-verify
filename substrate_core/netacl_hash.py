"""substrate_core.netacl_hash — BUCKETER cheap per il NetAcl-ledger (recall-only, MAI la prova).

Fingerprint del COMPORTAMENTO via campionamento DETERMINISTICO derivato dallo SCHEMA (non dal ruleset):
  H(ruleset) = SHA-256( risposte di decision_py su un set FISSO di pacchetti dello schema )
Proprieta' (sound per il bucketing): due rulesets EQUIVALENTI concordano su OGNI pacchetto -> stesse risposte ->
STESSO hash (mai un under-collapse di equivalenti). Il contrario NON e' garantito (due rulesets diversi possono
concordare sul campione -> stesso hash) -> e' un OVER-COLLAPSE, catturato e DEMOTATO dal giudice z3 (netacl_equiv).
Quindi un hash imperfetto costa solo RECALL, MAI soundness (la prova del collasso e' sempre il giudice).
NB: e' un fingerprint a campione, NON la forma canonica esatta (ROBDD) — onesto: v1, il giudice e' l'unico adjudicatore.
"""
from __future__ import annotations

import hashlib
import json
import random
from typing import Dict, List, Optional

from .domains.netacl_equiv import decision_py, ALLOW


def _schema_probe_packets(fields: Dict[str, int], n: int = 192, seed: int = 20260609) -> List[Dict[str, int]]:
    """Set FISSO di pacchetti, funzione del solo SCHEMA (cosi' rulesets equivalenti -> stesse risposte -> stesso hash)."""
    rng = random.Random(seed)
    keys = sorted(fields)
    pkts: List[Dict[str, int]] = []
    for k in keys:                               # confini per-campo (gli altri a 0)
        hib = (1 << fields[k]) - 1
        for v in (0, hib, hib // 2, 1):
            pkts.append({kk: (v if kk == k else 0) for kk in keys})
    for _ in range(n):                           # random deterministico su tutto lo schema
        pkts.append({k: rng.randint(0, (1 << fields[k]) - 1) for k in keys})
    return pkts


def netacl_semantic_hash(ruleset, fields: Dict[str, int], default: str) -> Optional[str]:
    """Hash comportamentale (bucketer). None se il ruleset non e' valutabile (-> non bucketizzato, all-pairs z3)."""
    try:
        pkts = _schema_probe_packets(fields)
        resp = "".join("1" if decision_py(ruleset, default, p) == ALLOW else "0" for p in pkts)
    except Exception:  # noqa
        return None
    schema = json.dumps({k: fields[k] for k in sorted(fields)}, separators=(",", ":"))
    return hashlib.sha256(("NETv1|" + schema + "|" + default + "|" + resp).encode("utf-8")).hexdigest()


__all__ = ["netacl_semantic_hash"]
