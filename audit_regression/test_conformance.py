"""Oracle for the SPEC v0.1.0 CONFORMANCE golden-vector suite. FROZEN content_hashes pin the canonicalization:
any drift (a 3rd-party verifier, or a future code change) that produces a different hash is non-conformant.
Cross-language guarantee: sha256(embedded canonical bytes) == content_hash (a JS/any verifier conforms)."""
import os, sys, json, hashlib
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from substrate_core import conformance as C

# FROZEN (computed once; a change here means the cert canonicalization changed -> cross-impl break)
FROZEN = {
    "confirmed-empirical": "87dc93b4e29e7c18bf29804b22ad1a990a80464155b0833c84704e0dc332c447",
    "refuted-proven": "70530df4d978b610bd7643b99e50bdd9fe7b74bd489525e7c0016106e5f8ab45",
    "abstain-typed": "b49b68dbcd5515dc7211598a673f6879bfac233860a8396af431e9d8289e21bf",
    "bounded-wasm": "324ab1a923622419fce2583c09bb465dcbdb26b004c956071b4d4d5b4ab1de1d",
    "unicode-reason": "88e204dfe8922de15e2a215857cc6fec830974e5dc094f153f20e5c6908f6d86",
}
FROZEN_PUBKEY = "16a4a594b9679c177d49b39911b7a447cf2b0a59d308bf87413fad54ea30fd17"
fails = []

if C.PUBKEY != FROZEN_PUBKEY:
    fails.append(f"conformance pubkey drift: {C.PUBKEY}")

vecs = C.golden_vectors()
# (1) frozen content_hashes — canonicalization is pinned
for v in vecs:
    if FROZEN.get(v["name"]) != v["content_hash"]:
        fails.append(f"[{v['name']}] content_hash drift {v['content_hash']} != frozen {FROZEN.get(v['name'])}")

# (2) cross-language: sha256(embedded canonical bytes) == content_hash (any-language verifier conforms)
for v in vecs:
    if hashlib.sha256(v["canonical"].encode("utf-8")).hexdigest() != v["content_hash"]:
        fails.append(f"[{v['name']}] sha256(canonical) != content_hash (cross-language determinism broken)")
    # and the embedded canonical must parse back to the cert minus stamp (the JS 'binding' check)
    if json.loads(v["canonical"]).get("verdict", {}).get("status") not in ("CONFIRMED", "REFUTED", "ABSTAIN"):
        fails.append(f"[{v['name']}] canonical does not parse to a valid verdict")

# (3) self-conformance: default impl passes hash + sig for every vector
if not C.check_conformance()["conformant"]:
    fails.append("default implementation is not self-conformant (hash/sig)")

# (4) the suite CATCHES a non-conformant 3rd-party: a broken hash_fn -> conformant False
broken = C.check_conformance(hash_fn=lambda b: hashlib.sha256(b + b"X").hexdigest())
if broken["conformant"]:
    fails.append("conformance suite failed to flag a non-conformant (wrong-hash) implementation")

# (5) tamper: mutating a cert body changes its canonical hash -> a conformant verifier rejects it
v0 = vecs[0]
body = json.loads(v0["canonical"]); body["verdict"]["status"] = "REFUTED"
if hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest() == v0["content_hash"]:
    fails.append("tampered cert produced the same content_hash (collision?!)")

if fails:
    print("FAIL test_conformance:"); [print("  -", f) for f in fails]; sys.exit(1)
print(f"PASS test_conformance: {len(vecs)} SPEC v0.1.0 golden vectors, frozen hashes + cross-language sha256(canonical) "
      "+ self-conformant + flags non-conformant impls + tamper-detect")
