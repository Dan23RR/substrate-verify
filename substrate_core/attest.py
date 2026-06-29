"""substrate_core.attest — INTEROP STANDARD: un certificato substrate <-> attestazione in-toto v1 in busta DSSE.

Perche' enterprise/world-class: per essere ADOTTATO, un verdetto non puo' vivere in un formato proprietario — deve
entrare nell'ecosistema supply-chain esistente (Sigstore/cosign, rekor, policy-controller, slsa-verifier). Qui un
verdetto substrate diventa un'attestazione **in-toto v1 Statement** (un nuovo predicateType) avvolta in **DSSE**
(Dead Simple Signing Envelope) firmata Ed25519 col PAE ESATTO da spec -> un verificatore DSSE/in-toto terzo la accetta.

PERIFERIA, non TCB: usa solo l'Ed25519 del kernel (puro) + base64/json (stdlib). Onesto: NON dichiariamo un livello
SLSA (SLSA misura la PROVENANCE di build, non un verdetto di verifica); il tier substrate viaggia nel predicate.
"""
from __future__ import annotations

import base64
import json
from typing import Optional

from .kernel import _privkey_from_seed, _pubkey_obj, derive_pubkey

IN_TOTO_TYPE = "https://in-toto.io/Statement/v1"
PREDICATE_TYPE = "https://substrate-core.dev/verdict/v0.1"
DSSE_PAYLOAD_TYPE = "application/vnd.in-toto+json"


def _pae(payload_type: bytes, body: bytes) -> bytes:
    """Pre-Authentication Encoding di DSSE (ESATTO da spec): cio' che si firma. Spec-compliant -> interop con cosign."""
    return (b"DSSEv1 " + str(len(payload_type)).encode() + b" " + payload_type
            + b" " + str(len(body)).encode() + b" " + body)


def _b64(b: bytes) -> str:
    return base64.standard_b64encode(b).decode("ascii")


def _b64d(s) -> bytes:
    """Decode CANONICO+STRICT (recon 2026-06-05, red-team F1/F2): accetta l'alfabeto standard O url-safe (DSSE:
    'verifiers MUST accept either') ma RIFIUTA whitespace/forme non-canoniche (validate=True) -> niente buste
    malleabili (unicita' per transparency-log / content-address)."""
    if isinstance(s, str):
        s = s.encode("ascii")   # non-ascii -> errore (rifiutato)
    last = None
    for cand in (s, s.translate(bytes.maketrans(b"-_", b"+/"))):
        try:
            return base64.b64decode(cand, validate=True)
        except Exception as e:  # noqa
            last = e
    raise ValueError(f"base64 non canonico (ne' standard ne' url-safe strict): {last}")


def to_statement(env: dict, *, subject_digest: Optional[str] = None) -> dict:
    """Mappa una busta-certificato substrate in un in-toto v1 Statement (subject = artefatto; predicate = verdetto)."""
    cert = env["certificate"]
    claim, vd = cert["claim"], cert["verdict"]
    digest = subject_digest or env.get("content_hash")
    return {
        "_type": IN_TOTO_TYPE,
        "subject": [{"name": str(claim.get("target", "")), "digest": {"sha256": digest}}],
        "predicateType": PREDICATE_TYPE,
        "predicate": {
            "status": vd.get("status"), "assurance": vd.get("assurance", "none"),
            "executed": vd.get("executed"), "domain": claim.get("domain"), "kind": claim.get("kind"),
            "content_hash": env.get("content_hash"), "engine": cert.get("engine"),
            "witness": vd.get("witness", {}), "reproduce": vd.get("reproduce", ""),
            "residual_risk": vd.get("residual_risk"), "assurance_caveat": vd.get("assurance_caveat", ""),
            "coverage": vd.get("coverage", {}), "spec": "substrate_core/SPEC v0.1.0",
        },
    }


def to_attestation(env: dict, *, key: bytes, subject_digest: Optional[str] = None) -> dict:
    """Busta DSSE firmata che avvolge l'in-toto Statement. Pronta per cosign/rekor/policy-controller."""
    body = json.dumps(to_statement(env, subject_digest=subject_digest),
                      sort_keys=True, separators=(",", ":")).encode("utf-8")
    ptype = DSSE_PAYLOAD_TYPE.encode("utf-8")
    sig = _privkey_from_seed(key).sign(_pae(ptype, body))
    return {"payloadType": DSSE_PAYLOAD_TYPE, "payload": _b64(body),
            "signatures": [{"keyid": derive_pubkey(key), "sig": _b64(sig)}]}


def verify_attestation(dsse: dict, *, pubkey: str) -> dict:
    """Verifica DSSE (ri-firma il PAE, mai un'eccezione -> bool) e restituisce lo Statement. Solo pubkey -> no conio."""
    try:
        body = _b64d(dsse["payload"])                       # canonico+strict, standard|url-safe (F1/F2)
        ptype = str(dsse["payloadType"]).encode("utf-8")
    except Exception:  # noqa
        return {"verified": False, "statement": None, "reason": "busta DSSE malformata / base64 non canonico"}
    pae = _pae(ptype, body)
    ok = False
    for s in (dsse.get("signatures") or []):
        try:
            _pubkey_obj(pubkey).verify(_b64d(s["sig"]), pae)
            ok = True
            break
        except Exception:  # noqa
            continue
    if not ok:
        # FOOTGUN chiuso: NON restituiamo lo statement parsato se non e' verificato (un consumer non deve leggerlo).
        return {"verified": False, "statement": None, "reason": "nessuna firma valida sotto la pubkey fornita"}
    statement = json.loads(body)
    subj = ((statement.get("subject") or [{}])[0].get("digest", {}) or {}).get("sha256")
    pred_ch = (statement.get("predicate", {}) or {}).get("content_hash")
    # F3: esponiamo la relazione subject<->content_hash cosi' un consumer in-toto (che keya sul subject) la vede.
    return {"verified": True, "statement": statement, "payloadType": dsse.get("payloadType"),
            "subject_digest": subj, "predicate_content_hash": pred_ch,
            "subject_matches_content_hash": (subj == pred_ch)}
