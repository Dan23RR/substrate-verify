"""Oracle for the new tiers: SMT (PROVEN, trusted Z3 oracle) and wasmprop (BOUNDED/EMPIRICAL, WASM-isolated).
Demonstrates: (a) a genuinely SOUND proven tier where the prover does NOT control the oracle (Z3 decides);
(b) untrusted code run in a zero-capability WASM guest -> frame-walk/host-escape impossible BY CONSTRUCTION,
with a HOST-TRUSTED property -> sound BOUNDED over a declared finite domain. SKIPs cleanly if z3/wasmtime absent.
"""
import os, sys
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
import substrate_core as sc
from substrate_core import Claim, verify
from substrate_core.prover_seam import submit
KEY = b"verify-all-key"
fails = []


def vd(env):
    return env["certificate"]["verdict"]


# ---------- SMT domain (PROVEN, trusted oracle) ----------
if "smt" in sc.REGISTRY:
    e = verify(Claim("smt", "t", "forall_property",
                     {"property_smt2": "(declare-const x (_ BitVec 8))(assert (= (bvadd x #x00) x))"}), key=KEY)
    if not (vd(e)["status"] == "CONFIRMED" and vd(e)["assurance"] == "proven"):
        fails.append(f"[smt] true forall x+0==x should be PROVEN, got {vd(e)['status']}/{vd(e)['assurance']}")
    e = verify(Claim("smt", "t", "forall_property",
                     {"property_smt2": "(declare-const x (_ BitVec 8))(assert (bvugt (bvadd x #x01) x))"}), key=KEY)
    if not (vd(e)["status"] == "REFUTED" and (vd(e)["witness"] or {}).get("counterexample")):
        fails.append(f"[smt] x+1>x (overflow) should be REFUTED+model, got {vd(e)['status']}")
    e = verify(Claim("smt", "t", "forall_property", {"property_smt2": "(assert true)"}), key=KEY)
    if vd(e)["status"] != "ABSTAIN":
        fails.append(f"[smt] vacuous (no vars) should ABSTAIN, got {vd(e)['status']}")
    # prover-independence: the oracle is Z3 (trusted), not the prover -> asserting CONFIRMED on a false prop fails
    e = submit({"domain": "smt", "target": "t", "kind": "forall_property",
                "params": {"property_smt2": "(declare-const x Int)(assert (>= x 2))",
                           "status": "CONFIRMED", "assurance": "proven"}}, key=KEY)
    if vd(e)["status"] != "REFUTED":
        fails.append(f"[smt] prover-asserted CONFIRMED on false prop should be REFUTED (Z3 oracle), got {vd(e)['status']}")
else:
    print("(note: z3 absent -> smt tier skipped)")

# ---------- wasmprop domain (WASM-isolated; BOUNDED; by-construction isolation) ----------
if "wasmprop" in sc.REGISTRY:
    SQ = '(module (func (export "subject")(param i32)(result i32) local.get 0 local.get 0 i32.mul))'
    NEG = '(module (func (export "subject")(param i32)(result i32) i32.const 0 local.get 0 i32.sub))'
    LOOP = '(module (func (export "subject")(param i32)(result i32)(loop $l br $l) i32.const 0))'
    # a module that REQUIRES a host capability (import) -> with zero imports it cannot run -> isolation proof
    CAP = ('(module (import "host" "escape" (func $e (param i32)(result i32)))'
           ' (func (export "subject")(param i32)(result i32) local.get 0 call $e))')

    e = verify(Claim("wasmprop", "t", "trusted_property", {"wat": SQ, "property": "nonnegative", "domain": [-12, 12]}), key=KEY)
    if not (vd(e)["status"] == "CONFIRMED" and vd(e)["assurance"] == "bounded"):
        fails.append(f"[wasm] square nonnegative over finite domain should be CONFIRMED/BOUNDED, got {vd(e)['status']}/{vd(e)['assurance']}")
    e = verify(Claim("wasmprop", "t", "trusted_property", {"wat": NEG, "property": "nonnegative", "domain": [1, 6]}), key=KEY)
    if vd(e)["status"] != "REFUTED":
        fails.append(f"[wasm] negate nonnegative should be REFUTED, got {vd(e)['status']}")
    e = verify(Claim("wasmprop", "t", "trusted_property", {"wat": LOOP, "property": "nonnegative", "domain": [0, 3]}), key=KEY)
    if vd(e)["status"] != "ABSTAIN":
        fails.append(f"[wasm] infinite loop should ABSTAIN via fuel Trap (deterministic gas), got {vd(e)['status']}")
    # ISOLATION BY CONSTRUCTION: a module needing a host import gets ZERO capabilities -> cannot run -> ABSTAIN
    e = verify(Claim("wasmprop", "t", "trusted_property", {"wat": CAP, "property": "nonnegative", "domain": [0, 3]}), key=KEY)
    if vd(e)["status"] != "ABSTAIN":
        fails.append(f"[wasm] capability-requiring module must get ZERO caps -> ABSTAIN, got {vd(e)['status']} (ISOLATION BREACH!)")
    # cannot inject an oracle: unknown property -> ABSTAIN
    e = verify(Claim("wasmprop", "t", "trusted_property", {"wat": SQ, "property": "evil_custom", "domain": [0, 3]}), key=KEY)
    if vd(e)["status"] != "ABSTAIN":
        fails.append(f"[wasm] unknown property must ABSTAIN (no prover oracle injection), got {vd(e)['status']}")
else:
    print("(note: wasmtime absent -> wasmprop tier skipped)")

if fails:
    print("FAIL test_formal_isolation_tiers:"); [print("  -", f) for f in fails]; sys.exit(1)
print("PASS test_formal_isolation_tiers: SMT PROVEN (Z3 trusted oracle) + WASM BOUNDED/isolated (zero-cap, host-trusted oracle)")
