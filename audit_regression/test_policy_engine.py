"""Oracle for the enterprise POLICY/admission engine. The unique feature: gating on substrate's HONEST tiers.
Shows: min-assurance floor, require_sound_confirm (DENY a prover-oracle empirical CONFIRMED, ALLOW a trusted-oracle
one), require_isolated, trusted_issuers (identity), require_status, signed+verifiable decisions, bundle policy.
SKIPs the smt/wasm legs cleanly if z3/wasmtime absent (pyprop legs always run)."""
import os, sys
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
import substrate_core as sc
from substrate_core import Claim, verify, derive_pubkey, CertGraph, policy
from substrate_core.export import export_bundle
KEY = b"verify-all-key"; PUB = derive_pubkey(KEY); EX = os.path.join(REPO, "examples")
fails = []


def dec(pol, env):
    return policy.evaluate(pol, env)["decision"]


e_emp = verify(Claim("pyprop", os.path.join(EX, "ex_abs.py"), "invariant", {"trials": 64}), key=KEY)   # CONFIRMED/empirical
e_ref = verify(Claim("pyprop", os.path.join(EX, "ex_buggy_sort.py"), "invariant", {"trials": 64}), key=KEY)  # REFUTED
e_proven = e_bounded = None
if "smt" in sc.REGISTRY:
    e_proven = verify(Claim("smt", "t", "forall_property",
                            {"property_smt2": "(declare-const x (_ BitVec 8))(assert (= (bvadd x #x00) x))"}), key=KEY)
if "wasmprop" in sc.REGISTRY:
    SQ = '(module (func (export "subject")(param i32)(result i32) local.get 0 local.get 0 i32.mul))'
    e_bounded = verify(Claim("wasmprop", "t", "trusted_property", {"wat": SQ, "property": "nonnegative", "domain": [-12, 12]}), key=KEY)

# NOTE (post red-team): field-gates require trusted_issuers (else any self-signed cert claims any tier). Sound policies pin PUB.
# min_assurance floor: empirical < bounded -> DENY
pol_floor = {"id": "min-bounded", "min_assurance": {"*": "bounded"}, "trusted_issuers": [PUB]}
if dec(pol_floor, e_emp) != "DENY":
    fails.append("min_assurance bounded should DENY a pyprop empirical CONFIRMED")
if e_bounded is not None and dec(pol_floor, e_bounded) != "ALLOW":
    fails.append("min_assurance bounded should ALLOW a wasmprop BOUNDED")
if e_proven is not None and dec(pol_floor, e_proven) != "ALLOW":
    fails.append("min_assurance bounded should ALLOW an smt PROVEN")

# require_sound_confirm: the HONESTY gate -> prover-oracle empirical CONFIRMED DENIED; trusted-oracle ALLOWED
pol_sound = {"id": "sound-only", "require_status": "CONFIRMED", "require_sound_confirm": True, "trusted_issuers": [PUB]}
if dec(pol_sound, e_emp) != "DENY":
    fails.append("require_sound_confirm should DENY a prover-oracle empirical CONFIRMED")
if e_proven is not None and dec(pol_sound, e_proven) != "ALLOW":
    fails.append("require_sound_confirm should ALLOW an smt PROVEN")

# require_isolated: wasmprop (isolated) ALLOW; pyprop (not isolated) DENY
pol_iso = {"id": "isolated", "require_isolated": True, "trusted_issuers": [PUB]}
if e_bounded is not None and dec(pol_iso, e_bounded) != "ALLOW":
    fails.append("require_isolated should ALLOW wasmprop (isolated)")
if dec(pol_iso, e_emp) != "DENY":
    fails.append("require_isolated should DENY pyprop (not isolated)")

# require_status -> a REFUTED is denied for a 'must be CONFIRMED' merge gate
if dec({"id": "must-confirm", "require_status": "CONFIRMED", "trusted_issuers": [PUB]}, e_ref) != "DENY":
    fails.append("require_status CONFIRMED should DENY a REFUTED")

# trusted_issuers (identity): KEY-signed ALLOW; foreign-issuer DENY
pol_iss = {"id": "trusted-iss", "trusted_issuers": [PUB]}
if dec(pol_iss, e_emp) != "ALLOW":
    fails.append("trusted_issuers should ALLOW the KEY-signed cert")
e_foreign = verify(Claim("pyprop", os.path.join(EX, "ex_abs.py"), "invariant", {"trials": 64}), key=b"other-issuer")
if dec(pol_iss, e_foreign) != "DENY":
    fails.append("trusted_issuers should DENY a foreign-issuer cert")

# signed, verifiable decision (auditable admission record)
sd = policy.signed_decision(pol_sound, e_emp, KEY)
if sd["decision"] != "DENY" or not policy.verify_decision(sd, pubkey=PUB):
    fails.append("signed_decision should be DENY and verify under issuer pubkey")
sd_t = dict(sd); sd_t["decision"] = "ALLOW"   # tamper the decision
if policy.verify_decision(sd_t, pubkey=PUB):
    fails.append("tampered decision still verified (signature binding broken)")

# bundle policy: a bundle with an empirical cert fails a min-bounded policy
g = CertGraph(pubkey=PUB); g.ingest(e_emp)
if e_proven is not None:
    g.ingest(e_proven)
b = export_bundle(g, key=KEY, name="pol")
if policy.evaluate_bundle(pol_floor, b)["decision"] != "DENY":
    fails.append("evaluate_bundle should DENY a bundle containing an empirical cert under min-bounded")

if fails:
    print("FAIL test_policy_engine:"); [print("  -", f) for f in fails]; sys.exit(1)
print("PASS test_policy_engine: tier-floor + sound-confirm (honesty gate) + isolated + status + trusted-issuer "
      "+ signed/verifiable decisions + bundle policy")
