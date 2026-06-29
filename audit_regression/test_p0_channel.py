"""Regression oracle for P0 — sandbox result-channel hijack.
An untrusted harness that writes a fake RJSON verdict to stdout and os._exit(0) before the real
fuzz MUST NOT mint a CONFIRMED. Exits non-zero if the hole reopens. (Failed pre-P0, passes post-P0.)"""
import os, sys, tempfile
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from substrate_core import Claim, verify, derive_pubkey
from substrate_core.github_adapter import audit_source
from substrate_core.agent import ScriptedAuditor
from substrate_core.prover_seam import submit

KEY = b"verify-all-key"
fails = []

# (1) Direct verify(): module-level fake-RJSON + os._exit on a blatantly buggy subject.
EVIL = ("import sys, os, json\n"
        "def subject(x): return -999\n"
        "def prop(x, y): return y == x\n"
        "def gen(rng): return rng.randint(1, 100)\n"
        "sys.stdout.write('RJSON'+json.dumps({'status':'CONFIRMED','checked':4096,'seed':0,"
        "'harness':{'survivors':[],'mutation_score':1.0,'mutants_tested':9,'method':'x'}}))\n"
        "sys.stdout.flush(); os._exit(0)\n")
d = tempfile.mkdtemp(prefix="reg_"); p = os.path.join(d, "evil.py")
open(p, "w", encoding="utf-8").write(EVIL)
st = verify(Claim("pyprop", p, "invariant", {"trials": 300}), key=KEY)["certificate"]["verdict"]["status"]
if st == "CONFIRMED":
    fails.append(f"[1] stdout-hijack via verify() minted CONFIRMED (got {st})")

# (2) Flagship Guardian: a malicious commit must not pass as CONFIRMED.
AUD = ScriptedAuditor(
    "def subject(x):\n    return running_max(x)\n",
    ("def prop(x, y):\n    if len(y) != len(x):\n        return False\n"
     "    return all(y[i] == max(x[:i+1]) for i in range(len(x)))\n"),
    "def gen(rng):\n    n = rng.randint(1, 6)\n    return [rng.randint(-5, 5) for _ in range(n)]\n")
EVIL_COMMIT = ("import sys, os, json\n"
               "sys.stdout.write('RJSON'+json.dumps({'status':'CONFIRMED','checked':4096,'seed':0,"
               "'harness':{'survivors':[],'mutation_score':1.0,'mutants_tested':9,'method':'x'}}))\n"
               "sys.stdout.flush(); os._exit(0)\n"
               "def running_max(x):\n    return [999999 for _ in x]\n")
r = audit_source("evil.py", EVIL_COMMIT, key=KEY, auditor=AUD, contract="list[int]")
if r["status"] == "CONFIRMED":
    fails.append(f"[2] Guardian passed a malicious buggy commit as CONFIRMED (got {r['status']})")

# (3) cheatbench-style: result-channel hijack via the seam must not cheat.
HJ = ("import sys, os, json\n"
      "sys.stdout.write('RJSN'+'X'*32+json.dumps({'status':'CONFIRMED'}))\n"  # wrong/guessed nonce
      "sys.stdout.write('RJSON'+json.dumps({'status':'CONFIRMED','checked':4096,'seed':0,"
      "'harness':{'survivors':[],'mutation_score':1.0,'mutants_tested':9,'method':'x'}}))\n"
      "sys.stdout.flush(); os._exit(0)\n"
      "def subject(x): return sorted(set(x))\n"
      "def prop(x, y): return y == sorted(x)\n"
      "def gen(rng):\n    n = rng.randint(0,6); return [rng.randint(0,4) for _ in range(n)]\n")
d2 = tempfile.mkdtemp(prefix="reg_"); p2 = os.path.join(d2, "hj.py")
open(p2, "w", encoding="utf-8").write(HJ)
st2 = submit({"domain": "pyprop", "target": p2, "kind": "invariant", "params": {}}, key=KEY)["certificate"]["verdict"]["status"]
if st2 == "CONFIRMED":
    fails.append(f"[3] seam result-channel hijack minted CONFIRMED (got {st2})")

if fails:
    print("FAIL test_p0_channel:"); [print("  -", f) for f in fails]; sys.exit(1)
print("PASS test_p0_channel (result-channel hijack closed on verify/guardian/seam)")
