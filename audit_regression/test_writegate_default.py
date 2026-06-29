"""Regression oracle — the DEFAULT CertGraph() must be authenticity-gated, not integrity-only.
A default graph must reject (a) an UNSIGNED envelope and (b) a body tampered + content_hash recomputed
(old signature no longer matches). (Fails pre-fix: today the default graph accepts both.)"""
import os, sys
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from substrate_core import CertGraph, ProvenanceError, Claim, verify
from substrate_core.kernel import cert_from_dict, content_hash

KEY = b"verify-all-key"
OK = os.path.join(REPO, "examples", "ex_abs.py")
fails = []

def rejects(env, label):
    try:
        CertGraph().ingest(env)
        return False
    except ProvenanceError:
        return True
    except Exception as e:   # any rejection is acceptable; a crash is not
        print(f"   ({label}: rejected via {type(e).__name__})"); return True

# (a) unsigned envelope (key=None -> sig=None, pubkey=None)
unsigned = verify(Claim("pyprop", OK, "invariant", {"trials": 64, "seed": 0}), key=None)
if not rejects(unsigned, "unsigned"):
    fails.append("default CertGraph() ACCEPTED an unsigned envelope")

# (b) body tampered + hash recomputed (old sig stays, must fail signature verification)
signed = verify(Claim("pyprop", OK, "invariant", {"trials": 64, "seed": 0}), key=KEY)
signed["certificate"]["verdict"]["reason"] = "TAMPERED BY ATTACKER"
signed["content_hash"] = content_hash(cert_from_dict(signed["certificate"]))  # honest re-hash
if not rejects(signed, "tamper+rehash"):
    fails.append("default CertGraph() ACCEPTED a body-tampered + rehashed envelope")

if fails:
    print("FAIL test_writegate_default:"); [print("  -", f) for f in fails]; sys.exit(1)
print("PASS test_writegate_default (default graph rejects unsigned + tamper-rehash)")
