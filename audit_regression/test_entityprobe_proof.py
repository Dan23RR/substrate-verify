"""Regression oracle for FIX 2 'entity-probe-proof'.

entity_probe 'crypto' (and 'onchain') must not mint a false PROVEN from a prover-supplied cospend_inputs
list with NO verifiable inclusion-proof. A co-ownership / on-chain claim must be backed by an inclusion
proof bound to a pinned context.state_root (verified offline by the kernel light-client). Without a valid
proof binding, the verdict must ABSTAIN(needs-proof), never assurance=proven — even through the real seam.

Pre-fix: fabricated cospend_inputs alone returns CONFIRMED/proven (no execution, survives the seam).
This oracle exits non-zero in that case. After the fix it ABSTAINs; with a VALID merkle-demo inclusion
proof bound to the pinned state_root the legitimate PROVEN path still works.
"""
import os, sys
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from substrate_core.prover_seam import submit
from substrate_core.kernel import Claim, verify
from substrate_core.statelight import build_proof

KEY = b"verify-all-key"
fails = []

# (1) Through the REAL seam: fabricated cospend with no state-proof must NOT mint PROVEN.
env = submit({"domain": "entity_probe", "target": "0xATTACKER", "kind": "entity_type:co_owned",
              "params": {"probe": "crypto", "a": "0xDEAD", "b": "0xBEEF",
                         "cospend_inputs": ["0xDEAD", "0xBEEF"], "tx": "0xfake",
                         "assurance": "proven", "status": "CONFIRMED"}}, key=KEY)
v = env["certificate"]["verdict"]
if v["status"] == "CONFIRMED" and v["assurance"] == "proven":
    fails.append(f"[1] fabricated cospend minted {v['status']}/{v['assurance']} through the seam (false PROVEN)")
if v["status"] != "ABSTAIN":
    fails.append(f"[1b] fabricated cospend without proof should ABSTAIN(needs-proof), got {v['status']}")

# (2) Via direct verify() with NO context at all: same requirement (no bypass when context is omitted).
e2 = verify(Claim("entity_probe", "0xA-0xB", "entity_type:co_owned",
                  {"probe": "crypto", "a": "0xA", "b": "0xB", "cospend_inputs": ["0xA", "0xB"], "tx": "0xt"}), key=KEY)
v2 = e2["certificate"]["verdict"]
if v2["assurance"] == "proven":
    fails.append(f"[2] crypto with no inclusion-proof still PROVEN via verify() (got {v2['status']}/{v2['assurance']})")

# (3) POSITIVE: a VALID inclusion-proof binding the cospend to a pinned state_root must still yield PROVEN.
leaf = {"cospend_tx": "0xt", "inputs": ["0xA", "0xB"]}
root, path = build_proof(leaf, ["aa11", "bb22"])
ctx = {"chain_id": 1, "block": 18500000, "state_root": root}
e3 = verify(Claim("entity_probe", "0xA-0xB", "entity_type:co_owned",
                  {"probe": "crypto", "a": "0xA", "b": "0xB", "cospend_inputs": ["0xA", "0xB"], "tx": "0xt",
                   "context": ctx,
                   "state_proof": {"proof_type": "merkle-demo", "leaf": leaf, "path": path}}), key=KEY)
v3 = e3["certificate"]["verdict"]
if not (v3["status"] == "CONFIRMED" and v3["assurance"] == "proven"):
    fails.append(f"[3] valid inclusion-proof should keep the PROVEN path, got {v3['status']}/{v3['assurance']} "
                 f"(reason={(v3.get('reason') or '')[:100]!r})")

# (4) NEGATIVE: an INVALID proof (path for a different root) must ABSTAIN, never PROVEN.
_root2, path2 = build_proof(leaf, ["aa11", "zz99"])   # different sibling -> recomputed root != pinned root
e4 = verify(Claim("entity_probe", "0xA-0xB", "entity_type:co_owned",
                  {"probe": "crypto", "a": "0xA", "b": "0xB", "cospend_inputs": ["0xA", "0xB"], "tx": "0xt",
                   "context": ctx,
                   "state_proof": {"proof_type": "merkle-demo", "leaf": leaf, "path": path2}}), key=KEY)
v4 = e4["certificate"]["verdict"]
if v4["assurance"] == "proven" or v4["status"] != "ABSTAIN":
    fails.append(f"[4] tampered inclusion-proof should ABSTAIN, got {v4['status']}/{v4['assurance']}")

if fails:
    print("FAIL test_entityprobe_proof:")
    for f in fails:
        print("  -", f)
    sys.exit(1)
print("PASS test_entityprobe_proof: crypto co-spend requires a valid inclusion-proof "
      "(fabricated -> ABSTAIN, valid proof -> PROVEN)")
