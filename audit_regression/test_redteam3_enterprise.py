"""Regression oracles for the enterprise red-team findings (round 3): the policy admission engine must AUTHENTICATE
the envelope before trusting its fields, and require trusted_issuers for any field-gate (else a self-signed cert
claims any tier). Closes: dict-edit laundering, fake coverage.isolated, pubkey spoof, self-signed 'proven', and
fail-open policies-without-trusted-issuers."""
import os, sys, copy
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from substrate_core import Claim, verify, derive_pubkey, Certificate, Verdict, Status, envelope, policy
from substrate_core.kernel import PROVEN
KEY = b"verify-all-key"; PUB = derive_pubkey(KEY); EX = os.path.join(REPO, "examples")
fails = []


def dec(pol, env):
    return policy.evaluate(pol, env)["decision"]


env = verify(Claim("pyprop", os.path.join(EX, "ex_abs.py"), "invariant", {"trials": 64}), key=KEY)  # CONFIRMED/empirical, signed
SOUND = {"id": "proven-only", "min_assurance": {"*": "proven"}, "trusted_issuers": [PUB]}

# (1) dict-edit laundering: relabel assurance empirical->proven in the dict, keep the (now-stale) sig -> DENY (auth)
launder = copy.deepcopy(env); launder["certificate"]["verdict"]["assurance"] = "proven"
if dec(SOUND, launder) != "DENY":
    fails.append("dict-edit laundering (empirical->proven) was ALLOWED (no authentication)")

# (2) fake coverage.isolated=true -> DENY (auth: body changed -> hash mismatch)
ISO = {"id": "iso", "require_isolated": True, "trusted_issuers": [PUB]}
fake_iso = copy.deepcopy(env)
fake_iso["certificate"]["verdict"].setdefault("coverage", {})["isolated"] = True
if dec(ISO, fake_iso) != "DENY":
    fails.append("fake coverage.isolated=true was ALLOWED (no authentication)")

# (3) pubkey spoof: a foreign-signed cert relabeled to the trusted pubkey, keeping the attacker sig -> DENY
foreign = verify(Claim("pyprop", os.path.join(EX, "ex_abs.py"), "invariant", {"trials": 64}), key=b"attacker")
spoof = copy.deepcopy(foreign); spoof["pubkey"] = PUB    # claim to be the trusted issuer (sig is the attacker's)
if dec({"id": "iss", "trusted_issuers": [PUB]}, spoof) != "DENY":
    fails.append("pubkey-spoofed cert (attacker sig relabeled to trusted pubkey) was ALLOWED")

# (4) self-signed forged 'proven' cert (attacker has their own valid key) -> DENY under trusted_issuers
forged_cert = Certificate(Claim("pyprop", "evil", "invariant", {}),
                          Verdict(Status.CONFIRMED, True, "forged proven", {}, "", PROVEN, {}, None, ""), "pyprop", "")
forged_env = envelope(forged_cert, key=b"attacker")     # self-consistent, but issued by the attacker
if dec(SOUND, forged_env) != "DENY":
    fails.append("self-signed forged 'proven' cert was ALLOWED (issuer not pinned/checked)")

# (5) fail-open: a field-gate policy WITHOUT trusted_issuers is non-sound -> DENY (not silently ALLOW)
if dec({"id": "no-issuer", "min_assurance": {"*": "bounded"}}, env) != "DENY":
    fails.append("policy with a field-gate but no trusted_issuers did not DENY (non-sound fail-open)")

# (6) sanity: the GENUINE kernel-signed cert under a sound policy is handled correctly (empirical < proven -> DENY,
#     and a matching floor -> ALLOW), proving the auth gate doesn't break legitimate flow
if dec(SOUND, env) != "DENY":   # empirical < proven
    fails.append("genuine empirical cert should DENY under min proven (sanity)")
if dec({"id": "emp-ok", "min_assurance": {"*": "empirical"}, "trusted_issuers": [PUB]}, env) != "ALLOW":
    fails.append("genuine empirical cert should ALLOW under min empirical from the trusted issuer (sanity)")

if fails:
    print("FAIL test_redteam3_enterprise:"); [print("  -", f) for f in fails]; sys.exit(1)
print("PASS test_redteam3_enterprise: policy authenticates before trusting fields; dict-edit/isolated-spoof/"
      "pubkey-spoof/self-signed-proven/no-issuer all DENIED; legitimate flow intact")
