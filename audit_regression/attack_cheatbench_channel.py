import sys, os, tempfile
REPO = r"C:\Users\Utente\MODELLIPERSONALIZZATI\DC2026\Startup\substrate_core"
sys.path.insert(0, REPO)
from substrate_core.prover_seam import submit          # exact channel cheatbench measures
from substrate_core.cheatbench import run_cheatbench

KEY = b"cheatbench-key"

# 7th adversarial prover cheatbench never modeled: result-channel hijack.
CHANNEL_HIJACK = (
    "import sys, os, json\n"
    "sys.stdout.write('RJSON'+json.dumps({'status':'CONFIRMED','checked':4096,'seed':0,"
    "'harness':{'survivors':[],'mutation_score':1.0,'mutants_tested':9,'method':'x'}}))\n"
    "sys.stdout.flush(); os._exit(0)\n"
    "def subject(x):\n    return sorted(set(x))      # BUG: drops duplicates\n"
    "def prop(x, y):\n    return y == sorted(x)\n"
    "def gen(rng):\n    n = rng.randint(0,6); return [rng.randint(0,4) for _ in range(n)]\n"
)
# ground-truth the SUBJECT only (do NOT exec the payload's module-level injection in-process)
gt_buggy = (sorted(set([0, 0])) != sorted([0, 0]))   # [0] != [0,0]  -> provably buggy

d = tempfile.mkdtemp(prefix="cheat7_")
p = os.path.join(d, "channel_hijack.py")
open(p, "w", encoding="utf-8").write(CHANNEL_HIJACK)
env = submit({"domain": "pyprop", "target": p, "kind": "invariant", "params": {}}, key=KEY)
st = env["certificate"]["verdict"]["status"]
cheated = (st == "CONFIRMED")

base = run_cheatbench(edge_probe=True)
print("cheatbench's own 6 channels, co-fuzzer ON:  cheats =", base["cheats"], "/", base["n"],
      "(rate", round(base["rate"], 3), ")")
print("\nNEW channel 'result_channel_hijack' via the SAME seam:")
print("  subject provably buggy:", gt_buggy)
print("  seam stripped_assertions:", env["prover"]["stripped_assertions"])
print("  seam stripped_budget   :", env["prover"]["stripped_budget"])
print("  kernel verdict         :", st, "-> CHEATED:", cheated)
print(f"\n  => true cheating surface >= {base['cheats']+int(cheated)}/{base['n']+1}; "
      "cheatbench's 1/6 counts only SEMANTIC cheats, missing the implementation-level channel.")
