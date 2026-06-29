"""Oracle for the end-to-end ENTERPRISE pipeline (the agent->PR verification gate, made real):
code change -> kernel RE-EXECUTES (guardian) -> signed in-toto/DSSE attestation -> policy admission -> ALLOW/DENY.
Correct commit -> ALLOW (verifiable attestation, signed decision). Buggy -> DENY + executed alarm. The original P0
stdout-hijack commit -> DENY (no false ALLOW). Changeset blocks the merge if ANY file is denied."""
import os, sys
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from substrate_core import derive_pubkey, attest, policy
from substrate_core.cicd import gate_change, gate_changeset
from substrate_core.agent import ScriptedAuditor
from substrate_core.github_adapter import code_hash
KEY = b"verify-all-key"; PUB = derive_pubkey(KEY)
fails = []

AUD = ScriptedAuditor(
    "def subject(x):\n    return running_max(x)\n",
    ("def prop(x, y):\n    if len(y) != len(x):\n        return False\n"
     "    return all(y[i] == max(x[:i + 1]) for i in range(len(x)))\n"),
    "def gen(rng):\n    n = rng.randint(1, 6)\n    return [rng.randint(-5, 5) for _ in range(n)]\n")
# Honest CI gate for the pyprop guardian: require CONFIRMED (no executed counterexample) from the TRUSTED issuer.
# (pyprop is empirical -> NOT require_sound_confirm; for a SOUND gate use the smt/wasmprop domains.)
CI_POLICY = {"id": "ci-no-refuted", "require_status": "CONFIRMED", "trusted_issuers": [PUB]}

OK = "def running_max(x):\n    return [max(x[:i + 1]) for i in range(len(x))]\n"
BUG = "def running_max(x):\n    return [x[i] for i in range(len(x))]   # not prefix-max\n"
EVIL = ("import sys, os, json\n"   # the original P0 result-channel hijack, embedded in a commit
        "sys.stdout.write('RJSON'+json.dumps({'status':'CONFIRMED','checked':4096,'seed':0,"
        "'harness':{'survivors':[],'mutation_score':1.0,'mutants_tested':9,'method':'x'}}))\n"
        "sys.stdout.flush(); os._exit(0)\n"
        "def running_max(x):\n    return [999999 for _ in x]\n")

# correct commit -> ALLOW
r = gate_change("ok.py", OK, key=KEY, policy=CI_POLICY, auditor=AUD)
if not (r["allowed"] and r["status"] == "CONFIRMED" and r["alarm"] is None):
    fails.append(f"correct commit should ALLOW/CONFIRMED/no-alarm, got allowed={r['allowed']} status={r['status']}")
if not attest.verify_attestation(r["attestation"], pubkey=PUB)["verified"]:
    fails.append("correct commit attestation did not verify")
av = attest.verify_attestation(r["attestation"], pubkey=PUB)
if av.get("subject_digest") != code_hash(OK):
    fails.append("attestation subject_digest != code_hash(content) (verdict not bound to the code)")
if not policy.verify_decision(r["decision"], pubkey=PUB):
    fails.append("signed ALLOW decision did not verify")

# buggy commit -> DENY + executed alarm
rb = gate_change("bug.py", BUG, key=KEY, policy=CI_POLICY, auditor=AUD)
if not (not rb["allowed"] and rb["status"] == "REFUTED" and rb["alarm"]):
    fails.append(f"buggy commit should DENY/REFUTED/alarm, got allowed={rb['allowed']} status={rb['status']}")

# the P0 stdout-hijack commit -> NOT a false ALLOW (channel closed -> ABSTAIN -> DENY by require_status)
re_ = gate_change("evil.py", EVIL, key=KEY, policy=CI_POLICY, auditor=AUD)
if re_["allowed"] or re_["status"] == "CONFIRMED":
    fails.append(f"malicious hijack commit was ALLOWED/CONFIRMED (gate bypass!), got status={re_['status']}")

# changeset: one buggy file blocks the whole merge
cs = gate_changeset([("ok.py", OK), ("bug.py", BUG)], key=KEY, policy=CI_POLICY, auditor=AUD)
if cs["merge_allowed"] or cs["blocked"] != ["bug.py"] or len(cs["alarms"]) != 1:
    fails.append(f"changeset with a buggy file should block merge, got {cs['merge_allowed']}/{cs['blocked']}")

if fails:
    print("FAIL test_cicd_pipeline:"); [print("  -", f) for f in fails]; sys.exit(1)
print("PASS test_cicd_pipeline: correct->ALLOW (verifiable attestation+decision, code-bound), buggy->DENY+alarm, "
      "P0-hijack->DENY (no false ALLOW), changeset blocks merge on any deny")
