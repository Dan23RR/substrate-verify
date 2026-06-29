"""Regression oracle for FIX 5 'ads-cardinality'.
The set cardinality n must be AUTHENTICATED by the root. Otherwise a malicious server truncates n to prove a
PRESENT key ABSENT (hiding e.g. a sanctioned address) while verify_query says complete:True.
Pre-fix: the truncation attack returns complete:True. Post-fix: binding root=H(inner||n) breaks -> complete:False.
"""
import os, sys
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from substrate_core.ads import build_index, query, verify_query

fails = []
idx = build_index([("alpha", "clean"), ("beta", "clean"), ("zzz", "SANCTIONED_HIT")])  # zzz present at pos 2, n=3

# (honest) membership of the sanctioned key verifies, and is NOT reported absent
vm = verify_query(query(idx, "zzz"))
if not (vm["complete"] and not vm.get("absent")):
    fails.append(f"honest membership of 'zzz' broke: {vm}")
# (honest) a truly-absent key still proves absence
va = verify_query(query(idx, "mmm"))
if not (va["complete"] and va.get("absent")):
    fails.append(f"honest absence of 'mmm' broke: {va}")

# ATTACK: prove the PRESENT 'zzz' ABSENT by truncating n so beta@pos1 looks like the last leaf.
left_beta = query(idx, "beta")["matches"][0]            # genuine inclusion proof of beta@pos1
attack = {"key": "zzz", "root": idx["root"], "inner": idx["inner"], "n": 2,   # n TRUNCATED (real n=3)
          "axis": "target", "matches": [], "left": left_beta, "right": None}
res = verify_query(attack)
if res.get("complete"):
    fails.append("n-truncation hid a PRESENT sanctioned match while verify_query said complete:True")

# ATTACK 2: forge a self-consistent truncated root (root=H(inner||2)). The verifier PINS the authentic root,
# so a result whose root != the pinned authentic root must also be rejected by the caller; here we assert the
# binding itself ties n to root (changing n alone, keeping the authentic root, is caught above).
if not fails:
    print("PASS test_ads_cardinality: n is authenticated by the root (truncation -> complete:False)")
else:
    print("FAIL test_ads_cardinality:"); [print("  -", f) for f in fails]; sys.exit(1)
