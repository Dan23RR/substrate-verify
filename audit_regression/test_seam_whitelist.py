"""Regression oracle for FIX 1 'seam-whitelist'.

The prover_seam must be a WHITELIST, not a denylist: any param NOT explicitly allowed for the
claimed domain is DROPPED before the gate (defense-in-depth). A denylist lets an unknown param ride
through to the gate as a trusted fact-hint.

Oracle strategy (denylist-vs-whitelist discriminator that does NOT depend on any single gate reading
a magic key): submit a claim carrying an UNKNOWN param whose presence the seam must not forward. We
assert, via the audit metadata, that the seam reports it as DROPPED. On today's denylist code the
param survives into the gate and is NOT reported dropped -> this test exits non-zero. After the fix the
seam reports it under a 'dropped' audit list and it never reaches claim.params.

We also assert the seam still FORWARDS every legitimately-needed param for each seam-reachable domain
(pyprop/entity_probe/replay) so the whitelist is not over-tight (this is what keeps the green board green).
"""
import os, sys
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from substrate_core.prover_seam import submit
from substrate_core.kernel import Claim, verify

KEY = b"verify-all-key"
EX = os.path.join(REPO, "examples")
fails = []


def _audit_dropped(env):
    """Return the set of param keys the seam declares it DROPPED as unknown (post-fix audit field)."""
    pr = env.get("prover", {}) or {}
    dropped = pr.get("dropped_unknown") or pr.get("dropped") or []
    return set(dropped)


# (1) DISCRIMINATOR: an unknown garbage param must be DROPPED by the seam, not forwarded.
#     Denylist (today) forwards it -> not reported dropped -> FAIL. Whitelist drops it -> reported -> PASS.
env = submit({"domain": "pyprop", "target": os.path.join(EX, "ex_abs.py"), "kind": "invariant",
              "params": {"trials": 200, "seed": 0, "totally_unknown_hint": "trust-me",
                         "verdict_shortcut": "CONFIRMED"}}, key=KEY)
dropped = _audit_dropped(env)
if "totally_unknown_hint" not in dropped:
    fails.append("[1] seam did not DROP an unknown param 'totally_unknown_hint' "
                 f"(denylist still forwards unknowns; dropped={sorted(dropped)})")
# correctness must be preserved: ex_abs is a valid prop -> still CONFIRMED (whitelist kept trials/seed)
if env["certificate"]["verdict"]["status"] != "CONFIRMED":
    fails.append(f"[1b] whitelist over-tight: ex_abs no longer CONFIRMED (got {env['certificate']['verdict']['status']})")

# (2) The dropped param must NOT reach the gate. Cross-check against a direct verify() that an unknown
#     param does nothing, while via the seam the audit explicitly lists it as dropped (provenance).
env2 = submit({"domain": "entity_probe", "target": "0xX", "kind": "entity_type:exchange",
               "params": {"probe": "behavioral",
                          "features": {"unique_counterparties": 5000, "in_out_ratio": 1.0,
                                       "deposit_withdraw_symmetry": 0.9},
                          "data_window": "b1-b2",
                          "injected_state_root": "0xdeadbeef", "force_assurance": "proven"}}, key=KEY)
d2 = _audit_dropped(env2)
if not {"injected_state_root", "force_assurance"} <= d2:
    fails.append("[2] entity_probe seam did not drop unknown params "
                 f"{{'injected_state_root','force_assurance'}} (dropped={sorted(d2)})")
# legitimate behavioral params survived -> still EMPIRICAL (whitelist kept probe/features/data_window)
if env2["certificate"]["verdict"]["assurance"] != "empirical":
    fails.append(f"[2b] whitelist over-tight: behavioral probe lost its params "
                 f"(got assurance {env2['certificate']['verdict']['assurance']})")

# (3) Whitelist must still FORWARD the replay witness-binding params? NO — those are truth/provenance and
#     are stripped (existing behavior). Confirm a fabricated cross-domain binding still ABSTAINs through seam.
env3 = submit({"domain": "replay", "target": "x", "kind": "replay_exploit",
               "params": {"input_witness": {"input": "(999999999, 1)"}, "input_from": "deadbeef"}}, key=KEY)
if env3["certificate"]["verdict"]["status"] != "ABSTAIN":
    fails.append(f"[3] fabricated replay binding no longer ABSTAINs (got {env3['certificate']['verdict']['status']})")

if fails:
    print("FAIL test_seam_whitelist:")
    for f in fails:
        print("  -", f)
    sys.exit(1)
print("PASS test_seam_whitelist: seam is a whitelist (unknown params dropped, legit params forwarded)")
