"""Regression oracle for FIX 3 'erc4626-executed'.

When forge cannot actually run (FORGE_BIN points at a nonexistent binary), the erc4626 autowire fallback
must NOT mint CONFIRMED/immune with executed=True on a VULNERABLE vault. The honest outcome is ABSTAIN
with executed=False (the exec-gate never executed; the verdict came from the risk-scorer, not execution).

Today (pre-fix) this returns CONFIRMED / assurance=bounded / executed=True on VaultBalanceOf.sol (a vault
whose totalAssets() reads balanceOf directly -> donation-inflatable) -> a false negative AND a violated
'executed' contract. This test exits non-zero in that case.

The test SKIPs (exit 0) if verivault is not importable at all, since then there is no fallback to exercise.
"""
import os, sys
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

# Force forge to be unavailable BEFORE importing the domain / running the gate.
os.environ["FORGE_BIN"] = os.path.join(REPO, "audit_regression", "_no_such_forge_binary.exe")

from substrate_core.kernel import Claim, verify
import substrate_core as sc

if "erc4626" not in sc.REGISTRY:
    print("SKIP test_erc4626_executed: erc4626 domain not registered")
    sys.exit(0)
try:
    import verivault  # noqa
except Exception as e:  # noqa
    print(f"SKIP test_erc4626_executed: verivault not importable ({type(e).__name__})")
    sys.exit(0)

if not getattr(verivault, "__file__", None):
    # verivault resolved as a namespace package (not installed): no real gate to exercise.
    print("SKIP test_erc4626_executed: verivault not installed (run `pip install -e ./verivault`)")
    sys.exit(0)

gate_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(verivault.__file__))), "gate")
vuln = os.path.join(gate_dir, "targets", "VaultBalanceOf.sol")
if not os.path.exists(vuln):
    print("SKIP test_erc4626_executed: vulnerable target VaultBalanceOf.sol not found")
    sys.exit(0)

# AUTOWIRE FALLBACK: no result_key -> erc4626.gate() takes the autowire branch with the bundled facts.
env = verify(Claim("erc4626", vuln, "immunity:donation_inflation", {"gate": gate_dir}), key=b"verify-all-key")
v = env["certificate"]["verdict"]
st, asr, executed = v["status"], v.get("assurance"), v.get("executed")

fails = []
if st == "CONFIRMED":
    fails.append(f"minted CONFIRMED on a VULNERABLE vault with forge absent (false negative); assurance={asr}")
if executed is True:
    fails.append("verdict claims executed=True but forge never ran (violated 'executed' contract)")
if st != "ABSTAIN":
    fails.append(f"expected ABSTAIN when the exec-gate did not execute, got {st}")

if fails:
    print("FAIL test_erc4626_executed:")
    for f in fails:
        print("  -", f)
    print(f"  (status={st}, assurance={asr}, executed={executed}, reason={(v.get('reason') or '')[:120]!r})")
    sys.exit(1)
print(f"PASS test_erc4626_executed: vulnerable vault + no forge -> {st} executed={executed} (no false immune)")
