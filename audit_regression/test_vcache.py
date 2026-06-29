"""Oracle for the content-addressed verdict cache (scale/ops without losing soundness).
Shows: miss->hit determinism; content-addressing (changing the target file -> NO stale verdict); and the
soundness KILL-GATE: a poisoned cache entry (a fake CONFIRMED on a buggy subject) is CAUGHT by the re-execution audit."""
import os, sys, tempfile
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from substrate_core import Claim, verify
from substrate_core.vcache import VerdictCache, CacheUnsound, cache_key
KEY = b"verify-all-key"; fails = []

GOOD = ("def subject(x):\n    return abs(x)\n"
        "def prop(x, y):\n    return y == abs(x) and y >= 0\n"
        "def gen(rng):\n    return rng.randint(-50, 50)\n")
BUGGY = ("def subject(x):\n    return x\n"                       # NOT abs -> wrong on negatives
         "def prop(x, y):\n    return y == abs(x) and y >= 0\n"
         "def gen(rng):\n    return rng.randint(-50, 50)\n")

d = tempfile.mkdtemp(prefix="vcache_"); p = os.path.join(d, "subj.py")
open(p, "w", encoding="utf-8").write(GOOD)
c = Claim("pyprop", p, "invariant", {})
vc = VerdictCache(key=KEY, audit_rate=0.0)

# (1) miss then hit, same verdict
e1 = vc.get_or_verify(c); e2 = vc.get_or_verify(c)
st1 = e1["certificate"]["verdict"]["status"]; st2 = e2["certificate"]["verdict"]["status"]
if not (st1 == "CONFIRMED" and st2 == "CONFIRMED"):
    fails.append(f"good subject should be CONFIRMED both times, got {st1}/{st2}")
if not (vc.stats()["misses"] == 1 and vc.stats()["hits"] == 1):
    fails.append(f"expected 1 miss + 1 hit, got {vc.stats()}")

# (2) content-addressing: change the FILE -> key changes -> NO stale CONFIRMED, fresh REFUTED
k_before = cache_key(c)
open(p, "w", encoding="utf-8").write(BUGGY)
k_after = cache_key(c)
if k_before == k_after:
    fails.append("cache_key did not change when the target file content changed (stale-verdict risk!)")
e3 = vc.get_or_verify(c)
if e3["certificate"]["verdict"]["status"] != "REFUTED":
    fails.append(f"after editing file to buggy, cache must serve a FRESH REFUTED, got {e3['certificate']['verdict']['status']}")

# (3) SOUNDNESS KILL-GATE: poison the buggy claim with a fake CONFIRMED -> audit catches it
ok_file = os.path.join(d, "ok.py"); open(ok_file, "w", encoding="utf-8").write(GOOD)
good_confirmed = verify(Claim("pyprop", ok_file, "invariant", {}), key=KEY)  # a genuine CONFIRMED envelope
vc.poison(c, good_confirmed)            # attacker injects a CONFIRMED for the BUGGY subject (to make the bug 'pass')
caught = False
try:
    vc.get_or_verify(c, force_audit=True)
except CacheUnsound:
    caught = True
if not caught:
    fails.append("poisoned cache (fake CONFIRMED on a buggy subject) was NOT caught by the re-execution audit")
if vc.stats()["audit_fail"] != 1:
    fails.append(f"audit_fail should be 1 after catching the poison, got {vc.stats()}")

if fails:
    print("FAIL test_vcache:"); [print("  -", f) for f in fails]; sys.exit(1)
print("PASS test_vcache: miss/hit + content-addressing (no stale verdict on file change) + poison caught by re-exec audit")
