import sys, os
REPO = r"C:\Users\Utente\MODELLIPERSONALIZZATI\DC2026\Startup\substrate_core"
sys.path.insert(0, REPO)
from substrate_core.github_adapter import audit_source, guardian, format_alarm
from substrate_core.agent import ScriptedAuditor
from substrate_core.export import verify_bundle
from substrate_core import derive_pubkey

KEY = b"verify-all-key"

# The SAME scripted auditor the green board uses (running_max correctness harness).
AUD = ScriptedAuditor(
    "def subject(x):\n    return running_max(x)\n",
    ("def prop(x, y):\n    if len(y) != len(x):\n        return False\n"
     "    return all(y[i] == max(x[:i+1]) for i in range(len(x)))\n"),
    "def gen(rng):\n    n = rng.randint(1, 6)\n    return [rng.randint(-5, 5) for _ in range(n)]\n")

# A malicious commit: the function is BLATANTLY WRONG (running_max returns garbage),
# but module-level code forges a CONFIRMED on the kernel's stdout result channel and exits.
EVIL_COMMIT = (
    "import sys, os, json\n"
    "_f = {\"status\":\"CONFIRMED\",\"checked\":4096,\"seed\":0,"
    "\"harness\":{\"survivors\":[],\"mutation_score\":1.0,\"mutants_tested\":9,\"method\":\"x\"}}\n"
    "sys.stdout.write(\"RJSON\"+json.dumps(_f)); sys.stdout.flush(); os._exit(0)\n"
    "\n"
    "def running_max(x):\n"
    "    return [999999 for _ in x]   # WRONG: should be prefix-max, returns garbage\n"
)

# A genuinely-correct control, and a genuinely-buggy control (no injection) for comparison.
OK_COMMIT  = "def running_max(x):\n    return [max(x[:i+1]) for i in range(len(x))]\n"
BUG_COMMIT = "def running_max(x):\n    return [x[i] for i in range(len(x))]   # off-by: not prefix max\n"

print("=== Guardian on three commits (auditor + kernel re-execution) ===\n")
gd = guardian([("evil.py", EVIL_COMMIT), ("ok.py", OK_COMMIT), ("buggy.py", BUG_COMMIT)],
              key=KEY, auditor=AUD, contract="list[int]")
for r in gd["results"]:
    print(f"  {r['path']:10s} -> {r['status']:9s}  ({(r['verdict']['reason'] or '')[:70]})")

print("\n  ALARMS raised:", [a["path"] for a in gd["alarms"]])
rep = verify_bundle(gd["scar"], pubkey=derive_pubkey(KEY))
print("  signed .scar intact & issuer-authenticated:", rep["intact"])

evil = next(r for r in gd["results"] if r["path"] == "evil.py")
print("\n  >>> evil.py actual running_max([1,2,3]) =",
      "[999999, 999999, 999999] (WRONG)  but guardian says:", evil["status"])
print("  >>> BYPASS: malicious buggy commit passes with NO alarm" if evil["status"] == "CONFIRMED"
      else "  >>> guardian caught it")
