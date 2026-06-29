"""Regression oracles for round-2 crypto/memory fixes found by adversarial re-verification:
 (G) KeyRing revocation is DURABLE (re-adding a revoked key does not resurrect it).
 (F) CertGraph.load takes its trust anchor from the CALLER, never the in-file pubkey (no silent downgrade).
 (E) ads.verify_query(expected_root=...) rejects a forged self-consistent SUBSET (anchored completeness).
"""
import os, sys, json, tempfile
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from substrate_core import Claim, verify, derive_pubkey, CertGraph
from substrate_core.transparency import KeyRing
from substrate_core.ads import build_index, query, verify_query

KEY = b"verify-all-key"; PUB = derive_pubkey(KEY); EX = os.path.join(REPO, "examples")
fails = []

# (G) durable revocation
env = verify(Claim("pyprop", os.path.join(EX, "ex_abs.py"), "invariant", {"trials": 64}), key=KEY)
ring = KeyRing(); ring.add(PUB, not_before=0, not_after=10**18)
if not ring.verify_cert(env, 100):
    fails.append("[G] valid key should accept before revocation")
ring.revoke(PUB)
if ring.verify_cert(env, 100):
    fails.append("[G] revoked key still accepted")
ring.add(PUB, not_before=0, not_after=10**18)        # attacker re-adds the revoked key
if ring.valid_at(PUB, 100) or ring.verify_cert(env, 100):
    fails.append("[G] re-adding a revoked key RESURRECTED it (revocation not durable)")

# (F) load trust anchor from caller, not the file
g = CertGraph(pubkey=PUB)
for f in ("ex_abs.py", "ex_buggy_sort.py"):
    g.ingest(verify(Claim("pyprop", os.path.join(EX, f), "invariant", {"trials": 64}), key=KEY))
tmp = tempfile.mkdtemp(prefix="r2_"); path = os.path.join(tmp, "g.json")
g.save(path)
g2 = CertGraph.load(path, verify=True, pubkey=PUB)            # caller anchors with PUB
if g2.pubkey != PUB:
    fails.append("[F] load(pubkey=PUB) must keep PUB as the identity anchor")
g3 = CertGraph.load(path, verify=True)                       # NO pubkey passed
if g3.pubkey is not None:
    fails.append("[F] load() without pubkey must NOT adopt the in-file pubkey as identity anchor")
if getattr(g3, "_declared_pubkey", None) != PUB:
    fails.append("[F] the in-file pubkey should be retained only as informational _declared_pubkey")

# (E) anchored ADS completeness vs a forged self-consistent subset
idx = build_index([("alpha", "clean"), ("beta", "clean"), ("zzz", "SANCTIONED_HIT")])
authentic_root = idx["root"]
fidx = build_index([("alpha", "clean"), ("beta", "clean")])  # attacker's SUBSET index (zzz removed), own root
fq = query(fidx, "zzz")                                       # 'absent' under the subset's own self-consistent root
if not verify_query(fq).get("complete"):
    fails.append("[E] precondition: unanchored verify_query should accept the self-consistent subset (the weakness)")
if verify_query(fq, expected_root=authentic_root).get("complete"):
    fails.append("[E] ANCHORED verify_query accepted a forged subset (root mismatch not enforced)")
gq = query(idx, "zzz")
if not verify_query(gq, expected_root=authentic_root).get("complete"):
    fails.append("[E] anchored verify_query rejected the GENUINE membership answer")

if fails:
    print("FAIL test_round2_cryptomem:"); [print("  -", f) for f in fails]; sys.exit(1)
print("PASS test_round2_cryptomem: durable revocation + caller-anchored load + anchored ADS completeness")
