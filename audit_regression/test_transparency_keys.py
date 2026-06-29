"""Regression oracle for FIX 8 'transparency-keys' (prototype).
Append-only transparency log with signed tree heads + inclusion + consistency, and a keyring with
rotation/revocation. Asserts: STH signature verifies (and a wrong key fails), inclusion verifies (tamper
fails), append EXTENDS (consistency True) while a rewritten history is detected (consistency False),
and the keyring accepts only valid-in-window, non-revoked issuers.
"""
import os, sys
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from substrate_core import Claim, verify, derive_pubkey
from substrate_core.transparency import TransparencyLog, KeyRing, verify_signed_head, verify_inclusion

KEY = b"verify-all-key"
PUB = derive_pubkey(KEY)
EX = os.path.join(REPO, "examples")
fails = []


def chk(label, cond):
    if not cond:
        fails.append(label)


# real signed certs -> log their content_hashes
hs = [verify(Claim("pyprop", os.path.join(EX, f), "invariant", {"trials": 64, "seed": 0}), key=KEY)["content_hash"]
      for f in ("ex_abs.py", "ex_buggy_sort.py", "ex_vacuous.py")]
log = TransparencyLog(KEY)
for h in hs:
    log.append(h)

# (1) signed tree head
head = log.signed_head()
chk("STH signature verifies under issuer pubkey", verify_signed_head(head, PUB))
chk("STH signature FAILS under a wrong pubkey", not verify_signed_head(head, derive_pubkey(b"wrong")))
chk("STH size == number of appended leaves", head["size"] == 3)

# (2) inclusion proofs
p1 = log.inclusion_proof(1)
chk("inclusion proof of leaf 1 verifies against the STH root", verify_inclusion(p1, head["root"]))
bad = dict(p1); bad["leaf_src"] = "deadbeef"      # tamper the leaf
chk("tampered inclusion leaf -> inclusion FAILS", not verify_inclusion(bad, head["root"]))
bad2 = dict(p1); bad2["index"] = 0                # claim a different position
chk("wrong position -> inclusion FAILS", not verify_inclusion(bad2, head["root"]))

# (3) consistency: append more -> the log EXTENDS the old head (append-only)
h4 = verify(Claim("pyprop", os.path.join(EX, "ex_abs.py"), "invariant", {"trials": 64, "seed": 1}), key=KEY)["content_hash"]
log.append(h4)
chk("appending extends the prior head (consistency True)", log.consistency(head)["extends"])

# rewritten history: a log with a DIFFERENT early entry must NOT be consistent with the old head
forged = TransparencyLog(KEY)
for h in [hs[0][::-1], hs[1], hs[2]]:    # first leaf altered
    forged.append(h)
chk("rewritten early entry -> consistency detects it (extends False)", not forged.consistency(head)["extends"])

# (4) keyring: rotation window + revocation
env = verify(Claim("pyprop", os.path.join(EX, "ex_abs.py"), "invariant", {"trials": 64, "seed": 0}), key=KEY)
ring = KeyRing(); ring.add(PUB, not_before=100, not_after=200)
chk("cert accepted by a valid-in-window key (t=150)", ring.verify_cert(env, 150))
chk("cert rejected OUT of window (t=50)", not ring.verify_cert(env, 50))
chk("cert rejected OUT of window (t=250)", not ring.verify_cert(env, 250))
env_other = verify(Claim("pyprop", os.path.join(EX, "ex_abs.py"), "invariant", {"trials": 64}), key=b"other-issuer")
chk("cert from an UNKNOWN issuer rejected", not ring.verify_cert(env_other, 150))
ring.revoke(PUB)
chk("cert rejected after the key is REVOKED", not ring.verify_cert(env, 150))

if fails:
    print("FAIL test_transparency_keys:"); [print("  -", f) for f in fails]; sys.exit(1)
print("PASS test_transparency_keys: signed log (inclusion+consistency) + keyring (rotation+revocation) hold")
