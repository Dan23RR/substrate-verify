"""substrate_core.cicd — la PIPELINE ENTERPRISE end-to-end (il 'verification step' nel loop agente->PR, REALE).

Una modifica di codice  ->  il kernel RI-ESEGUE (GitHub Guardian)  ->  attestazione in-toto/DSSE FIRMATA (subject =
code_hash del diff)  ->  POLICY / admission gate  ->  decisione ALLOW/DENY FIRMATA e auditabile.

Compone pezzi GIA' red-teamed (guardian + attest + policy); PERIFERIA, TCB puro. E' la tesi 'trust layer for AI
software' resa eseguibile: un agente/PR non-fidato propone codice, il kernel lo adjudica per ESECUZIONE, e il merge
e' gateato da una policy che ammette SOLO verdetti firmati dall'emittente fidato (mai un'opinione, mai un self-sign)."""
from __future__ import annotations

from typing import Optional

from .github_adapter import audit_source, code_hash, format_alarm
from .attest import to_attestation
from .policy import signed_decision


def gate_change(path: str, content: str, *, key: bytes, policy: dict, auditor=None,
                contract: str = "list[int]", model: Optional[str] = None) -> dict:
    """Adjudica UNA modifica e applica la policy. Ritorna verdetto + attestazione DSSE + decisione firmata.
    'auditor' scriptato (offline/test) o LLMAuditor (live, serve ANTHROPIC_API_KEY). La policy DEVE pinnare
    trusted_issuers (= la pubkey dell'emittente) per essere sound (vedi policy.py)."""
    r = audit_source(path, content, key=key, auditor=auditor, model=model, contract=contract)
    env = r["envelope"]
    att = to_attestation(env, key=key, subject_digest=code_hash(content))   # subject = il codice ESATTO adjudicato
    decision = signed_decision(policy, env, key)
    return {"path": path, "status": r["status"], "func": r.get("func"), "verdict": r["verdict"],
            "envelope": env, "attestation": att, "decision": decision,
            "allowed": decision["decision"] == "ALLOW",
            "alarm": format_alarm(r) if r["status"] == "REFUTED" else None}


def gate_changeset(files, *, key: bytes, policy: dict, auditor=None, contract: str = "list[int]") -> dict:
    """Gatea un changeset (lista di (path, content)). MERGE ammesso SOLO se OGNI file e' ALLOW. Ritorna i blocchi."""
    results = [gate_change(p, c, key=key, policy=policy, auditor=auditor, contract=contract) for p, c in files]
    blocked = [r for r in results if not r["allowed"]]
    return {"merge_allowed": len(blocked) == 0, "n": len(results), "blocked": [r["path"] for r in blocked],
            "alarms": [r["alarm"] for r in results if r["alarm"]], "results": results}
