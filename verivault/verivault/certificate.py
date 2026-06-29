"""
verivault.certificate — serializzazione CANONICA + content-hash + firma del Certificate (PORTABILE, CONTESTABILE).

Il cuore verification-native (oggi era L0-prose nel README: "certificati firmati portabili"): un certificato ESCE come
ARTEFATTO che chiunque puo'
  (a) ri-serializzare in modo DETERMINISTICO  (canonical_json: sorted-keys, separators fissi),
  (b) verificarne l'INTEGRITA' via content-hash (sha256) — il tampering cambia l'hash,
  (c) RI-ESEGUIRE lo script citato (`verdict.script`) e UCCIDERE un claim falso (la refutazione e' una feature).
Firma HMAC-SHA256 OPZIONALE: la chiave viene SOLO da env `VERIVAULT_SIGNING_KEY`, mai in codice/chat.

Disciplina: niente dipendenze esterne (stdlib). Round-trip stabile: from_dict(to_dict(c)) ha lo stesso canonical_json.
"""
from __future__ import annotations
import json, hashlib, hmac, os
from dataclasses import asdict
from .schemas import Claim, Verdict, Certificate, Status

SCHEMA_VERSION = "verivault-cert/1"


def to_dict(cert: Certificate) -> dict:
    """Certificate -> dict canonico (Status Enum -> stringa del suo valore)."""
    d = asdict(cert)
    d["verdict"]["status"] = cert.verdict.status.value     # Enum -> "PASS" | "REFUTED" | "ABSTAIN"
    d["_schema"] = SCHEMA_VERSION
    return d


def canonical_json(cert: Certificate) -> str:
    """Serializzazione DETERMINISTICA (stessa per chiunque) -> base di hash e firma."""
    return json.dumps(to_dict(cert), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def content_hash(cert: Certificate) -> str:
    """sha256 del canonical_json: identita'/integrita' del certificato (provenance)."""
    return hashlib.sha256(canonical_json(cert).encode("utf-8")).hexdigest()


def from_dict(d: dict) -> Certificate:
    """Ricostruisce un Certificate da dict (round-trip). Tollerante ai campi opzionali assenti."""
    cl, ve = d["claim"], d["verdict"]
    claim = Claim(kind=cl["kind"], payload=cl.get("payload", {}), oracle=cl["oracle"],
                  target=cl["target"], deps=cl.get("deps", []))
    verdict = Verdict(status=Status(ve["status"]), confidence=ve.get("confidence", 0.0),
                      counterexample=ve.get("counterexample"), proof=ve.get("proof"),
                      reason=ve.get("reason", ""), script=ve.get("script", ""), cost=ve.get("cost", {}))
    return Certificate(claim, verdict, composed_from=d.get("composed_from", []))


def _key(key: bytes | None) -> bytes:
    key = key or (os.environ.get("VERIVAULT_SIGNING_KEY", "").encode("utf-8") or None)
    if not key:
        raise RuntimeError("VERIVAULT_SIGNING_KEY non impostata (env-var, MAI in codice/chat).")
    return key


def sign(cert: Certificate, key: bytes | None = None) -> str:
    """Firma HMAC-SHA256 sul canonical_json. Portabile: viaggia col certificato."""
    return hmac.new(_key(key), canonical_json(cert).encode("utf-8"), hashlib.sha256).hexdigest()


def verify(cert: Certificate, signature: str, key: bytes | None = None) -> bool:
    """Verifica la firma in tempo costante. Tampering del certificato -> firma non valida."""
    return hmac.compare_digest(sign(cert, key), signature)


def envelope(cert: Certificate, key: bytes | None = None) -> dict:
    """Busta PORTABILE pronta all'export: certificato + hash + (se chiave) firma + schema."""
    env = {"schema": SCHEMA_VERSION, "certificate": to_dict(cert), "content_hash": content_hash(cert)}
    try:
        env["hmac_sha256"] = sign(cert, key)
    except RuntimeError:
        env["hmac_sha256"] = None      # firma opzionale: l'hash+script restano contestabili anche senza chiave
    return env
