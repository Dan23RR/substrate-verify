"""substrate_core.policy — POLICY / ADMISSION engine (la feature enterprise unica): gate un artefatto sui TIER
ONESTI di substrate. Pattern come Binary Authorization / Kyverno / sigstore policy-controller, MA il predicato che
nessun incumbent ha: "ammetti SOLO se il verdetto e' CONFIRMED a tier >= bounded e SOUND (oracolo fidato, non
empirico-del-prover) e da un esecutore ISOLATO, firmato da un emittente fidato e fresco". Decisione ALLOW/DENY
firmata e content-hashed -> record di admission auditabile e portabile. PERIFERIA (kernel.py resta puro).

Policy dichiarativa (dict):
  require_status        : "CONFIRMED" | [..]              (default: nessun vincolo)
  min_assurance         : {"<domain>": "bounded", "*": "empirical"}   (floor per-dominio, lattice-ordinato)
  require_sound_confirm : bool   (CONFIRMED deve essere bounded/proven-spec/proven, NON empirical-del-prover)
  require_isolated      : bool   (coverage.isolated == True: esecutore isolato, es. WASM zero-cap)
  trusted_issuers       : [pubkey, ..] | None   (identita': la pubkey della busta deve essere tra queste)
  max_residual_risk     : float | None
  allow_domains / deny_domains : [..]
  id                    : nome della policy (per l'audit)
"""
from __future__ import annotations

import hashlib
import json

from .kernel import (_ASSURANCE_RANK, derive_pubkey, _privkey_from_seed, _pubkey_obj,
                     cert_from_dict, content_hash, verify_sig)

_SOUND_TIERS = {"bounded", "proven-spec", "proven"}
# Una policy che legge QUALSIASI campo del verdetto e' enforce-abile SOLO se autentica la busta E pinna l'emittente
# (recon 2026-06-05, red-team): senza, un attaccante edita il dict (relabel assurance/coverage/pubkey) o auto-firma
# un cert che dichiara 'proven'. Questi gate richiedono trusted_issuers.
_GATE_KEYS = ("require_status", "min_assurance", "require_sound_confirm", "require_isolated",
              "max_residual_risk", "allow_domains", "deny_domains", "trusted_issuers")


def _rank(a: str) -> int:
    return _ASSURANCE_RANK.get(a, 0)


def _authenticate(env: dict, trusted_issuers):
    """Autentica la busta PRIMA di leggerne i campi: (1) hash ricomputato dal cert; (2) firma Ed25519 sotto la pubkey
    INCASTONATA; (3) se trusted_issuers e' pinnato, la pubkey dev'esservi (identita'). Chiude il dict-edit e l'auto-firma."""
    try:
        cert = cert_from_dict(env["certificate"])
    except Exception:  # noqa
        return False, "busta non ricostruibile"
    if content_hash(cert) != env.get("content_hash"):
        return False, "content_hash non combacia (corpo manomesso/relabel)"
    sig, pub = env.get("sig"), env.get("pubkey")
    if not sig or not pub:
        return False, "busta non firmata"
    if not verify_sig(cert, sig, pub):
        return False, "firma Ed25519 non valida sotto la pubkey incastonata (relabel/forgiatura)"
    if trusted_issuers is not None and pub not in set(trusted_issuers):
        return False, "emittente (pubkey) non in trusted_issuers"
    return True, ""


def evaluate(policy: dict, env: dict) -> dict:
    """Valuta UNA busta-certificato contro la policy -> {decision, reasons, ...}. DENY se QUALSIASI check fallisce.
    AUTENTICA la busta prima di fidarsi dei campi; i gate sui campi richiedono trusted_issuers (altrimenti non-sound)."""
    cert = env.get("certificate", {}) or {}
    claim, vd = cert.get("claim", {}) or {}, cert.get("verdict", {}) or {}
    dom, st, asr = claim.get("domain"), vd.get("status"), vd.get("assurance", "none")
    pid = policy.get("id", "unnamed")
    has_gates = any(policy.get(k) for k in _GATE_KEYS)
    ti = policy.get("trusted_issuers")

    # SOUNDNESS: un gate sui campi del verdetto e' privo di senso senza un emittente FIDATO (auto-firma banale).
    if has_gates and ti is None:
        return {"decision": "DENY", "reasons": ["policy NON-SOUND: i gate sui campi del verdetto richiedono "
                "trusted_issuers (altrimenti un emittente arbitrario auto-firma qualsiasi tier)"],
                "domain": dom, "status": st, "assurance": asr, "policy_id": pid}
    # AUTENTICA prima di leggere i campi (chiude dict-edit / relabel / forgiatura)
    if has_gates:
        ok, why = _authenticate(env, ti)
        if not ok:
            return {"decision": "DENY", "reasons": [f"NON AUTENTICATO: {why}"],
                    "domain": dom, "status": st, "assurance": asr, "policy_id": pid}

    reasons = []
    req_st = policy.get("require_status")
    if req_st:
        allowed = req_st if isinstance(req_st, (list, tuple, set)) else [req_st]
        if st not in allowed:
            reasons.append(f"status {st} non in {list(allowed)}")
    if dom in (policy.get("deny_domains") or []):
        reasons.append(f"dominio {dom} negato")
    ad = policy.get("allow_domains")
    if ad and dom not in ad:
        reasons.append(f"dominio {dom} non in allow_domains")
    ma = policy.get("min_assurance") or {}
    floor = ma.get(dom, ma.get("*"))
    if floor and _rank(asr) < _rank(floor):
        reasons.append(f"assurance {asr} < richiesto {floor} (dominio {dom})")
    if policy.get("require_sound_confirm") and not (st == "CONFIRMED" and asr in _SOUND_TIERS):
        reasons.append(f"require_sound_confirm: {st}/{asr} NON e' un CONFIRMED a oracolo-fidato (bounded/proven-spec/proven)")
    if policy.get("require_isolated") and not (vd.get("coverage", {}) or {}).get("isolated"):
        reasons.append("require_isolated: verdetto non da esecutore ISOLATO (coverage.isolated)")
    # (trusted_issuers e' gia' verificato in _authenticate, con la FIRMA — non basta leggere il campo pubkey)
    mr = policy.get("max_residual_risk")
    if mr is not None and (vd.get("residual_risk") is not None) and vd.get("residual_risk") > mr:
        reasons.append(f"residual_risk {vd.get('residual_risk')} > max {mr}")

    return {"decision": "ALLOW" if not reasons else "DENY", "reasons": reasons,
            "domain": dom, "status": st, "assurance": asr, "policy_id": policy.get("id", "unnamed")}


def evaluate_bundle(policy: dict, bundle: dict) -> dict:
    """Tutti i cert del bundle devono passare (ALLOW) -> bundle ALLOW; altrimenti DENY coi colpevoli."""
    certs = bundle.get("certs", {}) or {}
    per = {ch: evaluate(policy, env) for ch, env in certs.items()}
    ok = bool(per) and all(r["decision"] == "ALLOW" for r in per.values())
    return {"decision": "ALLOW" if ok else "DENY", "n": len(per),
            "denied": [ch for ch, r in per.items() if r["decision"] == "DENY"], "per_cert": per}


def _decision_body(d: dict, subject_content_hash) -> str:
    return json.dumps({"decision": d["decision"], "reasons": d["reasons"], "policy_id": d["policy_id"],
                       "subject_content_hash": subject_content_hash}, sort_keys=True, separators=(",", ":"))


def signed_decision(policy: dict, env: dict, key: bytes) -> dict:
    """La DECISIONE di admission, firmata Ed25519 + content-hashed: chi ha ammesso/negato COSA, ri-verificabile da un terzo."""
    d = evaluate(policy, env)
    sch = env.get("content_hash")
    dh = hashlib.sha256(_decision_body(d, sch).encode("utf-8")).hexdigest()
    sig = _privkey_from_seed(key).sign(dh.encode("utf-8")).hex()
    return {**d, "subject_content_hash": sch, "decision_hash": dh, "sig": sig, "pubkey": derive_pubkey(key)}


def verify_decision(signed: dict, *, pubkey: str) -> bool:
    """Ri-verifica una decisione firmata (solo pubkey -> nessun potere di conio). Mai eccezione -> bool."""
    try:
        dh = hashlib.sha256(_decision_body(signed, signed.get("subject_content_hash")).encode("utf-8")).hexdigest()
        if dh != signed.get("decision_hash"):
            return False
        _pubkey_obj(pubkey).verify(bytes.fromhex(signed["sig"]), dh.encode("utf-8"))
        return True
    except Exception:  # noqa
        return False
