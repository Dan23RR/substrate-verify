"""substrate_core.conformance — VETTORI GOLDEN per la conformita' allo SPEC v0.1.0.

Cosi' un formato diventa uno STANDARD (come i test-vector di Certificate-Transparency / Sigstore): una
implementazione TERZA del cert/.scar — segnatamente il verificatore JS nel browser — DEVE riprodurre ESATTAMENTE
questi content_hash e verificare queste firme Ed25519. I vettori sono costruiti A MANO (claim+verdict literali,
NON da un gate di dominio) cosi' sono deterministici PER SEMPRE, indipendenti da z3/wasmtime/forge.

Il check-chiave (zero-trust cross-linguaggio): SHA-256 dei BYTE CANONICI incastonati == content_hash. Un
verificatore in qualunque linguaggio che faccia sha256(canonical) ottiene lo stesso hash -> non re-implementa il
JSON di Python. PERIFERIA pura (solo kernel + hashlib)."""
from __future__ import annotations

import hashlib

from .kernel import (Claim, Verdict, Status, Certificate, content_hash, canonical_json, envelope,
                     verify_sig, derive_pubkey, EMPIRICAL, PROVEN, BOUNDED, NONE)

CONFORMANCE_SEED = b"substrate-conformance-v0.1.0"   # seed FISSO -> pubkey + firme deterministiche
PUBKEY = derive_pubkey(CONFORMANCE_SEED)


def _vectors_raw():
    """Certificati GOLDEN costruiti a mano: coprono la superficie dello SPEC (3 status, 3 tier, unicode, witness)."""
    return [
        ("confirmed-empirical", Certificate(
            Claim("pyprop", "ex_abs.py", "invariant", {"trials": 192, "seeds": [0, 1, 2]}),
            Verdict(Status.CONFIRMED, True, "no counterexample in 192 trials (empirical)",
                    {"trials_passed": 192}, "seed-sweep [0,1,2]", EMPIRICAL, {"method": "random-fuzz"}, 0.015625,
                    "rule-of-3 (95% CI)"), "pyprop", "")),
        ("refuted-proven", Certificate(
            Claim("pyprop", "ex_buggy_sort.py", "invariant", {}),
            Verdict(Status.REFUTED, True, "executed counterexample (claim false)",
                    {"input": "[3, 3]", "output": "[3]"}, "random.Random(0); trial 0", PROVEN,
                    {"counterexample_at_trial": 0}, None, ""), "pyprop", "")),
        ("abstain-typed", Certificate(
            Claim("pyprop", "missing.py", "invariant", {}),
            Verdict(Status.ABSTAIN, False, "file non trovato", {}, "", NONE, {}, None, ""), "kernel", "")),
        ("bounded-wasm", Certificate(
            Claim("wasmprop", "subject.wasm", "trusted_property", {"property": "nonnegative", "domain": [-12, 12]}),
            Verdict(Status.CONFIRMED, True, "exhaustive over declared domain", {"checked": 25, "exhaustive": True},
                    "wasmtime zero-cap", BOUNDED, {"isolated": True, "traps": 0}, None,
                    "BOUNDED: sound only within the declared finite domain"), "wasmprop", "")),
        ("unicode-reason", Certificate(
            Claim("smt", "forall-x", "forall_property", {}),
            Verdict(Status.CONFIRMED, True, "∀ input: proprietà válida — proven (città/naïve/π)",
                    {"smt_result": "unsat"}, "z3", PROVEN, {"oracle": "z3-trusted"}, None, "ünïcode caveat"),
            "smt", "")),
    ]


def golden_vectors():
    """Lista deterministica: {name, content_hash, canonical, envelope (firmato col seed di conformita')}."""
    out = []
    for name, cert in _vectors_raw():
        env = envelope(cert, key=CONFORMANCE_SEED)
        out.append({"name": name, "content_hash": env["content_hash"],
                    "canonical": canonical_json(cert), "envelope": env})
    return out


def check_conformance(hash_fn=None, sig_verify_fn=None) -> dict:
    """Verifica la conformita' di una implementazione TERZA. hash_fn(canonical_bytes)->hex (default: sha256);
    sig_verify_fn(content_hash, sig_hex, pubkey)->bool (default: Ed25519 del kernel). Ritorna pass/fail per vettore."""
    hf = hash_fn or (lambda b: hashlib.sha256(b).hexdigest())
    rows = []
    for v in golden_vectors():
        canon = v["canonical"].encode("utf-8")
        hash_ok = (hf(canon) == v["content_hash"])      # cross-linguaggio: sha256(canonical) == content_hash
        if sig_verify_fn is not None:
            sig_ok = bool(sig_verify_fn(v["content_hash"], v["envelope"]["sig"], PUBKEY))
        else:
            from .kernel import cert_from_dict
            sig_ok = verify_sig(cert_from_dict(v["envelope"]["certificate"]), v["envelope"]["sig"], PUBKEY)
        rows.append({"name": v["name"], "content_hash": v["content_hash"], "hash_ok": hash_ok, "sig_ok": sig_ok})
    return {"conformant": all(r["hash_ok"] and r["sig_ok"] for r in rows), "vectors": rows}
