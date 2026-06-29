"""compose_demo.py — algebra di composizione su verdetti SMT REALI (z3, pure-python).
Dimostra: (1) JOIN di immunita su piu regimi -> certificato whole-target SAFE con anello-debole;
(2) propagazione del REFUTE (una proprieta fallita -> tutto NON-safe); (3) MEET -> certificato VULN."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from verivault.oracles.smt_rounding import SmtRoundingOracle
from verivault.schemas import Claim, Certificate
from verivault.compose import join_safety, meet_vulnerability

smt = SmtRoundingOracle()

def smt_cert(kind, payload, target):
    claim = Claim(kind=kind, payload=payload, oracle="smt", target=target)
    return Certificate(claim, smt.decide(claim))

print("=" * 84)
print("ALGEBRA DI COMPOSIZIONE DEI CERTIFICATI (verdetti SMT/z3 reali)")
print("=" * 84)

# (1) JOIN: immunita di OZ-offset0 su 3 regimi di deposito-vittima -> certificato whole-target
oz_certs = []
for V in (1, 10**6, 10**18):
    oz_certs.append(smt_cert("erc4626.immunity",
        {"effective_offset_magnitude": 1, "victim_deposit": V, "max_donation_multiple": 100},
        "OZVault_offset0"))
whole = join_safety(oz_certs, "OZVault_offset0")
print("\n(1) JOIN immunita OZ-offset0 su V in {1, 1e6, 1e18}:")
for c in oz_certs:
    print(f"    foglia {c.claim.payload['victim_deposit']:>20}: {c.verdict.status.value}")
print(f"    => COMPOSITE: {whole.verdict.status.value} | emette={whole.emits} | {whole.verdict.proof}")

# (2) propagazione REFUTE: una proprieta fallita (raw trattato come claim-immunita -> REFUTED) uccide il safe-whole
raw_as_immunity = smt_cert("erc4626.immunity",
    {"effective_offset_magnitude": 0, "raw_pattern": True, "victim_deposit": 10**18, "max_donation_multiple": 100},
    "MixedVault")
mixed = join_safety([oz_certs[2], raw_as_immunity], "MixedVault")
print("\n(2) JOIN [immunita-OK, proprieta-RAW-fallita]:")
print(f"    foglia immunita: {oz_certs[2].verdict.status.value} | foglia raw: {raw_as_immunity.verdict.status.value}")
print(f"    => COMPOSITE: {mixed.verdict.status.value} | emette(safe)={mixed.emits} | {mixed.verdict.reason}")

# (3) MEET: claim-di-vulnerabilita raw (SMT witness) -> certificato VULN composto
raw_vuln = smt_cert("erc4626.donation_inflation",
    {"effective_offset_magnitude": 0, "raw_pattern": True, "victim_deposit": 10**18, "max_donation_multiple": 100},
    "RawVault")
vuln = meet_vulnerability([raw_vuln], "RawVault")
wit = (vuln.verdict.counterexample or {}).get("witnesses")
print("\n(3) MEET vulnerabilita raw (SMT witness):")
print(f"    => COMPOSITE: {vuln.verdict.status.value} | emette={vuln.emits} | witness={wit}")

print("\n" + "=" * 84)
print("Composizione: claim certificati -> certificato WHOLE-TARGET. JOIN=anello-debole, MEET=un-exploit-basta.")
print("REFUTED non esce mai come 'safe'; ABSTAIN dichiarato. Il gap che A1/aether/PoCo non coprono.")
