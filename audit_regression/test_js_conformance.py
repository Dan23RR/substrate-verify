"""Oracle: CROSS-LANGUAGE conformance proven EMPIRICALLY (not asserted). An independent JS/Node verifier (Node
SHA-256 + the shipped tweetnacl Ed25519 — the same primitives as the browser Lens) must reproduce the EXACT Python
content_hashes and verify the signatures for every SPEC v0.1.0 golden vector; a tampered vector must be rejected.
This closes the gap behind the .scar 'zero-trust in any language' claim. SKIPs if node / nacl.min.js absent."""
import os, sys, json, subprocess, tempfile, shutil
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from substrate_core import conformance as C

if not shutil.which("node"):
    print("SKIP test_js_conformance: node not on PATH"); sys.exit(0)
nacl = os.path.join(REPO, "verifier", "nacl.min.js")
checker = os.path.join(REPO, "audit_regression", "conformance_check.js")
if not (os.path.exists(nacl) and os.path.exists(checker)):
    print("SKIP test_js_conformance: nacl.min.js / checker missing"); sys.exit(0)

vecs = [{"name": v["name"], "content_hash": v["content_hash"], "canonical": v["canonical"],
         "sig": v["envelope"]["sig"], "pubkey": v["envelope"]["pubkey"]} for v in C.golden_vectors()]
d = tempfile.mkdtemp(prefix="jsconf_")
gp = os.path.join(d, "golden.json")
with open(gp, "w", encoding="utf-8") as f:
    json.dump(vecs, f)

fails = []
# (1) POSITIVE: the independent JS verifier reproduces all hashes + verifies all sigs
r = subprocess.run(["node", checker, gp, nacl], capture_output=True, text=True, timeout=60)
if r.returncode != 0 or "CONFORMANT" not in r.stdout or "NON-CONFORMANT" in r.stdout:
    fails.append(f"JS verifier did NOT reproduce Python hashes/sigs:\n{r.stdout}\n{r.stderr[:300]}")

# (2) NEGATIVE: a tampered content_hash -> the JS verifier must report non-conformant (exit!=0)
bad = json.loads(json.dumps(vecs)); bad[0]["content_hash"] = "00" * 32
gpb = os.path.join(d, "bad.json")
with open(gpb, "w", encoding="utf-8") as f:
    json.dump(bad, f)
rb = subprocess.run(["node", checker, gpb, nacl], capture_output=True, text=True, timeout=60)
if rb.returncode == 0 or "NON-CONFORMANT" not in rb.stdout:
    fails.append(f"JS verifier accepted a tampered content_hash (should reject):\n{rb.stdout}")

if fails:
    print("FAIL test_js_conformance:"); [print("  -", f) for f in fails]; sys.exit(1)
print(f"PASS test_js_conformance: independent JS/Node verifier (tweetnacl + SHA-256) reproduces all "
      f"{len(vecs)} SPEC golden content_hashes + verifies sigs; tampered vector rejected (cross-language determinism PROVEN)")
