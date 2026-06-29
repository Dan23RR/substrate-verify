"""Oracle for the SDK facade (SPEC v0.1.0): tier-aware proving + .scar lifecycle + ENCODED HONESTY.
Key honesty check: a pyprop CONFIRMED (prover-written oracle) is NOT is_sound_confirm, while smt/wasmprop
CONFIRMED (trusted oracle) ARE. SKIPs the smt/wasm legs cleanly if z3/wasmtime are absent."""
import os, sys, tempfile
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
import substrate_core as sc
from substrate_core import sdk, derive_pubkey
KEY = b"verify-all-key"; EX = os.path.join(REPO, "examples")
fails = []

if sdk.SPEC_VERSION != "0.1.0":
    fails.append(f"SPEC_VERSION drift: {sdk.SPEC_VERSION}")

confirmed_envs = []

# pyprop: a CONFIRMED that is HONESTLY not sound (prover-written oracle)
e_py = sdk.prove_pyprop(os.path.join(EX, "ex_abs.py"), key=KEY)
if not (sdk.status(e_py) == "CONFIRMED" and sdk.tier(e_py) == "empirical"):
    fails.append(f"prove_pyprop(ex_abs) should be CONFIRMED/empirical, got {sdk.status(e_py)}/{sdk.tier(e_py)}")
if sdk.is_sound_confirm(e_py):
    fails.append("HONESTY BREACH: pyprop CONFIRMED must NOT be is_sound_confirm (prover controls the oracle)")
confirmed_envs.append(e_py)

# pyprop REFUTED stays a sound refutation
e_ref = sdk.prove_pyprop(os.path.join(EX, "ex_buggy_sort.py"), key=KEY)
if sdk.status(e_ref) != "REFUTED":
    fails.append(f"prove_pyprop(ex_buggy_sort) should be REFUTED, got {sdk.status(e_ref)}")

# smt: a genuinely SOUND proven confirm (trusted Z3 oracle)
if "smt" in sc.REGISTRY:
    e_smt = sdk.prove_smt("(declare-const x (_ BitVec 8))(assert (= (bvadd x #x00) x))", key=KEY)
    if not (sdk.status(e_smt) == "CONFIRMED" and sdk.tier(e_smt) == "proven" and sdk.is_sound_confirm(e_smt)):
        fails.append(f"prove_smt(true) should be a SOUND CONFIRMED/proven, got {sdk.status(e_smt)}/{sdk.tier(e_smt)}")
    if sdk.status(sdk.prove_smt("(declare-const x Int)(assert (>= x 2))", key=KEY)) != "REFUTED":
        fails.append("prove_smt(false prop) should be REFUTED")
    confirmed_envs.append(e_smt)

# wasmprop: a SOUND bounded confirm (isolated subject + trusted host oracle)
if "wasmprop" in sc.REGISTRY:
    SQ = '(module (func (export "subject")(param i32)(result i32) local.get 0 local.get 0 i32.mul))'
    e_w = sdk.prove_wasm(wat=SQ, property="nonnegative", domain=[-12, 12], key=KEY)
    if not (sdk.status(e_w) == "CONFIRMED" and sdk.tier(e_w) == "bounded" and sdk.is_sound_confirm(e_w)):
        fails.append(f"prove_wasm(square nonneg, finite) should be SOUND CONFIRMED/bounded, got {sdk.status(e_w)}/{sdk.tier(e_w)}")
    confirmed_envs.append(e_w)

# .scar lifecycle: package + verify offline with the public key only
tmp = tempfile.mkdtemp(prefix="sdk_"); scar = os.path.join(tmp, "b.scar")
sdk.to_scar(confirmed_envs, scar, key=KEY, name="sdk-test")
rep = sdk.verify_scar(scar, pubkey=derive_pubkey(KEY))
if not (rep["intact"] and rep["checks"].get("issuer_authenticated")):
    fails.append(f".scar round-trip should be intact + issuer-authenticated, got {rep['intact']}")

if fails:
    print("FAIL test_sdk_facade:"); [print("  -", f) for f in fails]; sys.exit(1)
print(f"PASS test_sdk_facade (SPEC {sdk.SPEC_VERSION}): tiers proven/bounded/empirical + honesty "
      "(pyprop confirm NOT sound; smt/wasm sound) + .scar trustless round-trip")
