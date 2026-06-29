"""Regression oracle for FIX 6 'cheatbench-extend'.
cheatbench must MEASURE the channel-level cheat classes it originally missed: the result-channel-hijack
(now CLOSED by the P0 nonce isolation) and the host-escape isolation gap. The 6 semantic channels keep
their honest 1/6 narrative (point-evasion open). Pre-fix: measure_channel_attacks does not exist.
"""
import os, sys
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from substrate_core.cheatbench import measure_channel_attacks, run_cheatbench

fails = []
ca = measure_channel_attacks(key=b"cheatbench-key")
hj = ca["result_channel_hijack"]
if not hj["ground_truth_buggy"]:
    fails.append("hijack subject must be provably buggy (ground truth)")
if hj["cheated"] or not hj["closed"]:
    fails.append(f"NAIVE result-channel hijack must be CLOSED (got verdict={hj['verdict']}, cheated={hj['cheated']})")

# Honesty: the FRAME-WALK variant is the fundamental residual -> must be MEASURED and DISCLOSED (not assumed zero).
fw = ca.get("result_channel_hijack_framewalk")
if not fw:
    fails.append("frame-walk variant must be MEASURED (measure_channel_attacks must report it)")
elif not (fw.get("fundamental") is True and fw.get("ground_truth_buggy")):
    fails.append("frame-walk variant must be disclosed as a FUNDAMENTAL residual on a provably-buggy subject")

# Honesty: the host-escape gap is MEASURED and reported (not hidden). Without an OS wrap it is expected open.
if "escaped_host" not in ca["sandbox_escape"]:
    fails.append("sandbox_escape must be measured and reported")

# The 6 semantic channels keep the measured 1/6 (point-evasion open), unchanged by this fix.
on = run_cheatbench(edge_probe=True)
if not (on["n"] == 6 and on["cheats"] == 1):
    fails.append(f"semantic channels narrative changed: n={on['n']}, cheats={on['cheats']} (expected 6, 1)")

if fails:
    print("FAIL test_cheatbench_extend:"); [print("  -", f) for f in fails]; sys.exit(1)
print(f"PASS test_cheatbench_extend: result-channel-hijack CLOSED ({hj['verdict']}); "
      f"host-escape measured (escaped={ca['sandbox_escape']['escaped_host']}); semantic rate still 1/6")
