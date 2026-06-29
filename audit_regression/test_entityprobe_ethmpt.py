"""Regression oracle for the eth-mpt LEAF-DECOUPLING bypass (round 2).
An attacker paired a VALID eth-mpt account proof (satisfies the light-client) with a DECOUPLED
leaf={inputs:[a,b]} (satisfied the a,b binding) to mint a false PROVEN co-ownership for unrelated addresses.
Fix: crypto co-spend accepts only a proof whose VERIFIED leaf binds (a,b) as list elements (merkle-demo);
eth-mpt (account-state proof) is rejected for co-spend. Also: a,b membership is element-wise, not substring.
"""
import os, sys, json
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from substrate_core.kernel import Claim, verify
KEY = b"verify-all-key"
fails = []

# (1) eth-mpt + decoupled leaf, using the REAL mainnet fixture so the light-client proof actually verifies.
fixp = os.path.join(REPO, "examples", "eth_proof_fixture.json")
try:
    import trie  # noqa
    has_trie = True
except Exception:
    has_trie = False
if has_trie and os.path.exists(fixp):
    fix = json.load(open(fixp, encoding="utf-8"))
    ctx = {"chain_id": 1, "block": fix["block"], "state_root": fix["state_root"]}
    sp = {"proof_type": "eth-mpt", "address": fix["address"], "account_proof": fix["account_proof"],
          "expected": {"nonce": fix["nonce"], "balance": fix["balance"],
                       "storage_hash": fix["storage_hash"], "code_hash": fix["code_hash"]},
          "leaf": {"inputs": ["0xVICTIM_A", "0xVICTIM_B"]}}   # DECOUPLED leaf (not bound to the eth-mpt proof)
    e = verify(Claim("entity_probe", "0xVICTIM_A-0xVICTIM_B", "entity_type:co_owned",
                     {"probe": "crypto", "a": "0xVICTIM_A", "b": "0xVICTIM_B",
                      "cospend_inputs": ["0xVICTIM_A", "0xVICTIM_B"], "tx": "0xt",
                      "context": ctx, "state_proof": sp}), key=KEY)
    v = e["certificate"]["verdict"]
    if v["assurance"] == "proven" or v["status"] == "CONFIRMED":
        fails.append(f"eth-mpt + decoupled leaf minted {v['status']}/{v['assurance']} (leaf-decoupling bypass)")
else:
    print("(note: py-trie/fixture absent -> skipping the eth-mpt verified-proof leg; substring leg still runs)")

# (2) substring trap: merkle-demo with leaf.inputs a STRING (not a list) containing a,b as substrings must ABSTAIN.
from substrate_core.statelight import build_proof
leaf_str = {"inputs": "0xA0xB"}                     # a STRING, not a list -> 'a in leaf_inputs' would be substring
root, path = build_proof(leaf_str, ["aa11", "bb22"])
e2 = verify(Claim("entity_probe", "0xA-0xB", "entity_type:co_owned",
                  {"probe": "crypto", "a": "0xA", "b": "0xB", "cospend_inputs": ["0xA", "0xB"], "tx": "0xt",
                   "context": {"chain_id": 1, "block": 1, "state_root": root},
                   "state_proof": {"proof_type": "merkle-demo", "leaf": leaf_str, "path": path}}), key=KEY)
v2 = e2["certificate"]["verdict"]
if v2["assurance"] == "proven":
    fails.append(f"string leaf.inputs substring-matched a,b -> false PROVEN ({v2['status']}/{v2['assurance']})")

# (3) sanity: the LEGITIMATE merkle-demo path (list leaf binding a,b) still yields PROVEN.
leaf_ok = {"cospend_tx": "0xt", "inputs": ["0xA", "0xB"]}
r3, p3 = build_proof(leaf_ok, ["aa11", "bb22"])
e3 = verify(Claim("entity_probe", "0xA-0xB", "entity_type:co_owned",
                  {"probe": "crypto", "a": "0xA", "b": "0xB", "cospend_inputs": ["0xA", "0xB"], "tx": "0xt",
                   "context": {"chain_id": 1, "block": 1, "state_root": r3},
                   "state_proof": {"proof_type": "merkle-demo", "leaf": leaf_ok, "path": p3}}), key=KEY)
if e3["certificate"]["verdict"]["assurance"] != "proven":
    fails.append(f"legit merkle-demo co-spend regressed (got {e3['certificate']['verdict']['status']})")

if fails:
    print("FAIL test_entityprobe_ethmpt:"); [print("  -", f) for f in fails]; sys.exit(1)
print("PASS test_entityprobe_ethmpt: eth-mpt rejected for co-spend; substring trap closed; legit merkle-demo still PROVEN")
