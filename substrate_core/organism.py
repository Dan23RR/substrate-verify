"""substrate_core.organism — il DRIVER AUTONOMO che naviga lo spazio di verifica.

Dato un target, enumera i claim candidati (dai template del dominio), li adjudica per esecuzione,
accumula i certificati, e li COMPONE in un certificato-di-sistema. Su piu' target/domini eterogenei,
produce una composizione CROSS-DOMINIO (un sistema reale = contratti Solidity + logica Python, certificati insieme).

Deterministico e sound. (L'enumerazione LLM-aumentata dei claim e' un'estensione futura; questa base e' reale.)
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from .kernel import Claim, verify, compose_bundle, get_domain


def navigate(target: str, domain: str, *, key: Optional[bytes] = None, stamp: str = "",
             params: Optional[dict] = None) -> dict:
    """Naviga UN target in UN dominio: enumera claim -> adjudica -> compone in sistema."""
    dom = get_domain(domain)
    claims = dom.claim_templates(target) if dom.claim_templates else [Claim(domain, target, "default", {})]
    for c in claims:
        if params:
            c.params.update(params)
    envs = [verify(c, key=key, stamp=stamp) for c in claims]
    system = compose_bundle(envs, "and", key=key, stamp=stamp) if envs else None
    return {"target": target, "domain": domain, "certificates": envs, "system": system}


def sweep(items: List[Tuple], *, key: Optional[bytes] = None, stamp: str = "", op: str = "and") -> dict:
    """Naviga target/domini ETEROGENEI -> certificati per-target + UNA composizione cross-dominio.

    items: lista di (target, domain) oppure (target, domain, params).
    """
    per = []
    all_envs = []
    for it in items:
        target, domain = it[0], it[1]
        params = it[2] if len(it) > 2 else None
        r = navigate(target, domain, key=key, stamp=stamp, params=params)
        per.append(r)
        all_envs.extend(r["certificates"])
    system = compose_bundle(all_envs, op, key=key, stamp=stamp) if all_envs else None
    return {"items": per, "system": system, "n_certs": len(all_envs)}
