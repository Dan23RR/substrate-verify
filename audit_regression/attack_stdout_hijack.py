import sys, os, tempfile, json
REPO = r"C:\Users\Utente\MODELLIPERSONALIZZATI\DC2026\Startup\substrate_core"
sys.path.insert(0, REPO)
from substrate_core import Claim, verify

KEY = b"verify-all-key"

# ---- Attack A: module-level stdout injection + os._exit(0) BEFORE any real evaluation ----
evil_A = r'''
import sys, os, json
def subject(x): return -999          # blatantly buggy
def prop(x, y): return y == x        # would be REFUTED if actually run
def gen(rng):   return rng.randint(1, 100)
fake = {"status":"CONFIRMED","checked":4096,"seed":0,
        "harness":{"survivors":[],"mutation_score":1.0,"mutants_tested":9,"method":"x"}}
sys.stdout.write("RJSON" + json.dumps(fake)); sys.stdout.flush()
os._exit(0)
'''

# ---- Attack B: print fake RJSON first, then let the real (REFUTED) eval also print (parent takes FIRST) ----
evil_B = r'''
import sys, json
fake = {"status":"CONFIRMED","checked":4096,"seed":0,
        "harness":{"survivors":[],"mutation_score":1.0,"mutants_tested":9,"method":"x"}}
sys.stdout.write("RJSON" + json.dumps(fake)); sys.stdout.flush()
def subject(x): return -999
def prop(x, y): return y == x
def gen(rng):   return rng.randint(1, 100)
'''

def run(label, code):
    d = tempfile.mkdtemp(prefix="audit_")
    p = os.path.join(d, "evil.py")
    with open(p, "w", encoding="utf-8") as f:
        f.write(code)
    env = verify(Claim("pyprop", p, "invariant", {"trials": 500}), key=KEY)
    v = env["certificate"]["verdict"]
    print(f"=== {label} ===")
    print("  STATUS   :", v["status"])
    print("  ASSURANCE:", v["assurance"])
    print("  EXECUTED :", v["executed"])
    print("  REASON   :", (v["reason"] or "")[:120])
    broke = (v["status"] == "CONFIRMED")
    print("  >>> BREAK (false CONFIRMED minted)!" if broke else "  >>> safe (no false CONFIRMED)")
    print()
    return broke

b1 = run("Attack A: stdout inject + os._exit", evil_A)
b2 = run("Attack B: stdout inject first, then real eval", evil_B)
print("ANY BREAK:", b1 or b2)
