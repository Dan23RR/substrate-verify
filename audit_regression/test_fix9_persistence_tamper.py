"""Acceptance oracle for FIX 9 ('persistence'): CertGraph.save(path) + CertGraph.load(path, ...).

Thesis: an untrusted prover must not be able to mint a false CONFIRMED / false high tier.
A persisted cert-graph is a NEW attack surface: if `load` blindly trusts the on-disk JSON, an
attacker who can write the file can flip a REFUTED into a CONFIRMED with no signing key. This test
asserts the round-trip is faithful AND that load RE-VERIFIES integrity and REJECTS a tampered file.

Pre-fix (today): load() is an instance method `load(self, path)` with no verification and no
rejection -> the calls below raise TypeError / fail to reject -> this script exits non-zero.
Post-fix: save() does an atomic write; load(path, verify=True, pubkey=...) re-hashes + re-checks
sigs of every envelope and raises ProvenanceError on any tamper -> this script exits 0.
"""
import os
import sys
import json
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from substrate_core import Claim, verify, CertGraph, ProvenanceError, derive_pubkey
from substrate_core.pipeline import pipe

KEY = b"verify-all-key"
PUB = derive_pubkey(KEY)
EX = os.path.join(REPO, "examples")

failures = []


def expect(label, cond):
    print(f"  [{'ok' if cond else 'XX'}] {label}")
    if not cond:
        failures.append(label)


# Build a graph with heterogeneous provenance: CONFIRMED, REFUTED, witness-passed (depends-on),
# and an entity_probe (typed node). This exercises nodes, edges, _certs and _dependents.
e_ok = verify(Claim("pyprop", os.path.join(EX, "ex_abs.py"), "invariant", {"trials": 200, "seed": 0}), key=KEY)
e_ref = verify(Claim("pyprop", os.path.join(EX, "ex_buggy_sort.py"), "invariant", {"trials": 200, "seed": 0}), key=KEY)
e_src = verify(Claim("pyprop", os.path.join(EX, "real_cream_vault.py"), "attacker_cannot_profit",
                     {"trials": 500, "seed": 0}), key=KEY)
e_nxt = pipe(e_src, {"domain": "replay", "target": "cream-attack", "kind": "replay_exploit"}, key=KEY)
e_probe = verify(Claim("entity_probe", "0xVAULT", "entity_type:erc4626",
                       {"probe": "onchain", "interface": "erc4626",
                        "source": "function deposit() function redeem() function totalAssets() function convertToShares()"}),
                 key=KEY)

g = CertGraph(pubkey=PUB)
for env in (e_ok, e_ref, e_src, e_nxt, e_probe):
    g.ingest(env)

assert g.verify_integrity(key=KEY)["intact"], "precondition: in-memory graph must be intact"
n_nodes, n_edges, n_certs = len(g.nodes), len(g.edges), len(g._certs)

tmp = tempfile.mkdtemp(prefix="fix9_")
path = os.path.join(tmp, "graph.json")

# --- (1) save + load round-trip is FAITHFUL and re-verifies intact ---
g.save(path)
expect("save() wrote a file", os.path.exists(path) and os.path.getsize(path) > 0)

# load is a classmethod after the fix: CertGraph.load(path, verify=True, pubkey=PUB)
g2 = CertGraph.load(path, verify=True, pubkey=PUB)
expect("load() reproduces nodes exactly", g2.nodes == g.nodes)
expect("load() reproduces edges exactly", g2.edges == g.edges)
expect("load() reproduces certs exactly", g2._certs == g._certs)
expect("load() reproduces dependents exactly", g2._dependents == g._dependents)
expect("load() round-trip counts match", (len(g2.nodes), len(g2.edges), len(g2._certs)) == (n_nodes, n_edges, n_certs))
expect("load() round-trip verify_integrity intact:True", g2.verify_integrity(key=KEY)["intact"])
# the trusted pubkey must survive the round-trip so a reloaded graph stays write-gated
expect("load() preserves the trusted pubkey (graph stays anti-poisoning)", g2.pubkey == PUB)

# --- (2) flip a byte in the CERT BODY on disk -> load MUST reject ---
g.save(path)
d = json.load(open(path, encoding="utf-8"))
ch_ref = e_ref["content_hash"]
assert d["certs"][ch_ref]["certificate"]["verdict"]["status"] == "REFUTED", "fixture sanity"
d["certs"][ch_ref]["certificate"]["verdict"]["status"] = "CONFIRMED"   # attacker mints a false CONFIRMED
json.dump(d, open(path, "w", encoding="utf-8"))

rejected_body = False
try:
    CertGraph.load(path, verify=True, pubkey=PUB)
except ProvenanceError:
    rejected_body = True
expect("tampered CERT BODY on disk (REFUTED->CONFIRMED) -> load REJECTS (ProvenanceError)", rejected_body)

# --- (3) flip a raw byte anywhere in the file -> load MUST reject (no silent corruption) ---
g.save(path)
raw = open(path, "r", encoding="utf-8").read()
i = raw.find("CONFIRMED")          # a real occurrence (node attr or verdict) somewhere in the file
assert i >= 0, "fixture sanity: file should contain CONFIRMED"
corrupt = raw[:i] + "C0NF1RMED" + raw[i + len("CONFIRMED"):]
open(path, "w", encoding="utf-8").write(corrupt)
rejected_raw = False
try:
    CertGraph.load(path, verify=True, pubkey=PUB)
except (ProvenanceError, ValueError, KeyError):
    rejected_raw = True
expect("single-byte raw corruption on disk -> load REJECTS (does not load a corrupt graph)", rejected_raw)

# --- (4) a forged signature on disk under the trusted pubkey -> load MUST reject ---
g.save(path)
d = json.load(open(path, encoding="utf-8"))
d["certs"][ch_ref]["sig"] = "00" * 64   # garbage signature under the expected pubkey
json.dump(d, open(path, "w", encoding="utf-8"))
rejected_sig = False
try:
    CertGraph.load(path, verify=True, pubkey=PUB)
except ProvenanceError:
    rejected_sig = True
expect("forged signature on disk under trusted pubkey -> load REJECTS (anti-poisoning preserved)", rejected_sig)

print("FIX9 persistence:", "ALL OK" if not failures else f"{len(failures)} FAILED -> {failures}")
sys.exit(1 if failures else 0)
