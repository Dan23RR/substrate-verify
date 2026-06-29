"""Regression oracles for the red-team findings on the NEW tiers (round 2 of hardening):
 (SMT) SMT-LIB2 stateful parse-trick (push/pop/reset) that minted a false PROVEN -> now ABSTAIN.
 (WASM) trap-hiding: a subject that TRAPS on the 'bad' input (silently skipped) minted a false BOUNDED -> now
        ABSTAIN (any trap = incomplete coverage); secondary-call traps are no longer swallowed. SKIPs if z3/wasmtime absent.
"""
import os, sys
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
import substrate_core as sc
from substrate_core import Claim, verify
fails = []


def st(env):
    return env["certificate"]["verdict"]["status"]


# ---- SMT parse-trick (false PROVEN) ----
if "smt" in sc.REGISTRY:
    for label, s in [
        ("push/pop", "(declare-const x Int)(push)(assert (> x 0))(pop)(assert (= x x))"),
        ("reset", "(declare-const x Int)(assert (> x 0))(reset)(declare-const x Int)(assert (= x x))"),
        ("push/pop+comment", "(declare-const x Int)( ;c\n push)(assert (> x 0))(pop)(assert (= x x))"),
    ]:
        v = verify(Claim("smt", "t", "forall_property", {"property_smt2": s}), key=b"k")["certificate"]["verdict"]
        if v["status"] == "CONFIRMED":
            fails.append(f"[smt {label}] stateful parse-trick still mints CONFIRMED/{v['assurance']} (false PROVEN)")
    # legit cases unaffected
    if st(verify(Claim("smt", "t", "forall_property", {"property_smt2": "(declare-const x (_ BitVec 8))(assert (= (bvadd x #x00) x))"}), key=b"k")) != "CONFIRMED":
        fails.append("[smt] legit true forall regressed (should stay CONFIRMED/PROVEN)")

# ---- WASM trap-hiding (false BOUNDED) ----
if "wasmprop" in sc.REGISTRY:
    # subject traps (unreachable) on x<0, returns x on x>=0 -> hides the negative region for 'nonnegative'
    HIDE = ('(module (func (export "subject")(param i32)(result i32)'
            ' (if (i32.lt_s (local.get 0)(i32.const 0)) (then unreachable)) (local.get 0)))')
    v = verify(Claim("wasmprop", "t", "trusted_property", {"wat": HIDE, "property": "nonnegative", "domain": [-3, 3]}), key=b"k")
    if st(v) != "ABSTAIN":
        fails.append(f"[wasm trap-hide unreachable] should ABSTAIN (incomplete coverage), got {st(v)} (false BOUNDED!)")
    # div-by-zero trap on x==0 (realistic self-hiding bug)
    DIV = '(module (func (export "subject")(param i32)(result i32) (i32.div_s (i32.const 100)(local.get 0))))'
    v = verify(Claim("wasmprop", "t", "trusted_property", {"wat": DIV, "property": "bounded:0:1000", "domain": [0, 5]}), key=b"k")
    if st(v) != "ABSTAIN":
        fails.append(f"[wasm div0 trap-hide] should ABSTAIN (x=0 traps), got {st(v)}")
    # secondary-call trap not swallowed: subject(x)=x+10 (no primary trap on [0,3]); subject(output) traps (output>=10)
    SEC = ('(module (func (export "subject")(param i32)(result i32)'
           ' (if (i32.ge_s (local.get 0)(i32.const 10)) (then unreachable)) (i32.add (local.get 0)(i32.const 10))))')
    v = verify(Claim("wasmprop", "t", "trusted_property", {"wat": SEC, "property": "idempotent", "domain": [0, 3]}), key=b"k")
    if st(v) != "ABSTAIN":
        fails.append(f"[wasm secondary-trap idempotent] should ABSTAIN (2nd call traps, not swallowed), got {st(v)}")
    # legit cases unaffected (0 traps)
    SQ = '(module (func (export "subject")(param i32)(result i32) local.get 0 local.get 0 i32.mul))'
    v = verify(Claim("wasmprop", "t", "trusted_property", {"wat": SQ, "property": "nonnegative", "domain": [-12, 12]}), key=b"k")
    if not (st(v) == "CONFIRMED" and v["certificate"]["verdict"]["assurance"] == "bounded"):
        fails.append(f"[wasm legit] square nonneg finite should stay CONFIRMED/BOUNDED, got {st(v)}")

if fails:
    print("FAIL test_redteam2_fixes:"); [print("  -", f) for f in fails]; sys.exit(1)
print("PASS test_redteam2_fixes: SMT parse-trick -> ABSTAIN; WASM trap-hiding (primary/div0/secondary) -> ABSTAIN; legit intact")
