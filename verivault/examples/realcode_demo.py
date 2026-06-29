"""realcode_demo.py — LOOP END-TO-END SU CODICE REALE, harness PARAMETRICO generale (5 forme, 4 librerie upstream).
audit_realcode(target.sol) -> extract(LLM) -> score -> exec-gate REALE (forge, attacco fedele) -> certificato firmato.

I fatti sono estratti dall'LLM reale (sub-agent, NESSUNA key) e iniettati come llm_fact_fn (il Python non chiama l'LLM
senza key; restano output-LLM fedele). L'exec-gate gira DAVVERO sul vero Solmate/Solady/OZ via la loro ABI reale.

PUNTO CHIAVE: per Solady/OZ-offset0 lo SCORER e' conservativo (risk ~0.85), ma l'EXEC-GATE prova IMMUNE per esecuzione
-> il gate ha priorita (e' la prova, non l'euristica). E' il cuore verification-native.
"""
import os, sys
os.environ.setdefault("FORGE_BIN", r"C:\Users\Utente\.foundry\bin\forge.exe")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from verivault.pipeline import audit_realcode
from verivault.stage2_score import defense_risk

ROOT = r"C:\Users\Utente\MODELLIPERSONALIZZATI\DC2026\Startup\research_substrate_capacity\exp\virgin\gate"
GATE_TEST = "test/GeneralGate.t.sol"   # harness PARAMETRICO generale (5 forme)
T = os.path.join(ROOT, "targets")

# fatti estratti dall'LLM reale (sub-agent) sui sorgenti veri:
CASES = [
    ("Solmate balanceOf  (VULN)",     os.path.join(T, "VaultBalanceOf.sol"),  "solmate_balanceof",
     {"totalAssets_type": "external_balanceOf",  "effective_offset_magnitude": 0,       "dead_shares": False, "donation_vector": True,  "defense_strength": 0.0}),
    ("Solmate internal   (SAFE)",     os.path.join(T, "VaultInternal.sol"),   "solmate_internal",
     {"totalAssets_type": "internal_accounting", "effective_offset_magnitude": 0,       "dead_shares": False, "donation_vector": False, "defense_strength": 0.8}),
    ("Solady virtual-sh. (SAFE)",     os.path.join(T, "SoladyVault.sol"),     "solady_virtualshares",
     {"totalAssets_type": "external_balanceOf",  "effective_offset_magnitude": 1,       "dead_shares": False, "donation_vector": True,  "defense_strength": 0.85}),
    ("OZ offset0         (SAFE)",     os.path.join(T, "OZVault.sol"),         "oz_offset0",
     {"totalAssets_type": "external_balanceOf",  "effective_offset_magnitude": 1,       "dead_shares": False, "donation_vector": True,  "defense_strength": 0.85}),
    ("OZ offset6         (SAFE-forte)", os.path.join(T, "OZVaultOffset6.sol"), "oz_offset6",
     {"totalAssets_type": "external_balanceOf",  "effective_offset_magnitude": 1000000, "dead_shares": False, "donation_vector": True,  "defense_strength": 0.97}),
]

def stub(facts):
    return lambda src: dict(facts)

print("=" * 92)
print("LOOP END-TO-END su CODICE REALE — VeriVault.audit_realcode | harness PARAMETRICO (5 forme, 4 lib upstream)")
print("=" * 92)
print(f"{'forma':28} {'scorer-risk':>11} {'GATE (exec)':>12} {'emette':>7}  dettaglio")
for title, target, rkey, facts in CASES:
    risk, _ = defense_risk(facts)
    cert = audit_realcode(target, ROOT, GATE_TEST, rkey, llm_fact_fn=stub(facts))
    v = cert.verdict
    detail = ""
    if v.counterexample:
        cx = v.counterexample
        prof = cx.get("attacker_profit_wei") or cx.get("max_attacker_profit_wei")
        detail = f"VULN profit={int(prof)/1e18:.2f} tok, witness D*={int(cx.get('donation_witness_wei') or 0)/1e18:.0f}e18"
    elif v.proof and v.proof.get("immunity_certificate"):
        detail = f"IMMUNE (max profit attaccante = {v.proof.get('max_attacker_profit_wei')/1e18:+.2f} tok)"
    verdict_label = "VULN" if (cert.claim.kind.endswith("donation_inflation")) else ("IMMUNE" if v.proof else v.status.value)
    print(f"{title:28} {risk:>11.2f} {verdict_label:>12} {str(cert.emits):>7}  {detail}")

print("=" * 92)
print("Loop chiuso su CODICE REALE: sorgente -> fatti-LLM -> rischio -> ESECUZIONE forge fedele -> certificato.")
print("Nota: Solady/OZ-offset0 hanno scorer-risk 0.85 (euristica cauta) ma il GATE prova IMMUNE -> la PROVA vince.")
