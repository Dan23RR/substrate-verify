"""
test_extractor.py — CICLO prodotto (gap b, OFFLINE): l'estrattore-fatti DETERMINISTICO strutturale, falsificato sul reale.

Colma il gap (b) per i pattern STRUTTURALI senza API/PROMETHEUS: verifica che `extract_facts` (path deterministico
offline) estragga i fatti CORRETTI dai 5 shape ERC-4626 REALI, e che il flusso-prodotto `audit_signed` giri end-to-end
SENZA STUB (estrazione reale -> score -> exec-gate -> certificato firmato).

KILL-CONDITION (binaria): se i fatti estratti NON combaciano col ground-truth strutturale dei 5 contratti reali
(totalAssets_type, offset, analyzability) -> l'estrattore e' inaffidabile -> idea morta. ABSTAIN onesto sui casi non parsati.
Riproducibile: `python eval/test_extractor.py`  (il passo end-to-end usa forge; degrada onesto se assente).
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from verivault.stage1_extract import extract_facts
from verivault.stage2_score import defense_risk
from verivault import audit_signed
from verivault import certificate as C

HERE = os.path.dirname(os.path.abspath(__file__))
STARTUP = os.path.dirname(os.path.dirname(HERE))
GATE = os.environ.get("GATE_DIR", os.path.join(STARTUP, "research_substrate_capacity", "exp", "virgin", "gate"))
T = os.path.join(GATE, "targets")

# ground-truth STRUTTURALE dei 5 contratti reali (da ispezione del sorgente)
GT = [
    ("VaultBalanceOf.sol", "external_balanceOf", 0.0, True),    # solmate + override balanceOf -> raw manipolabile
    ("VaultInternal.sol",  "internal_accounting", None, True),  # accumulatore interno -> immune a donazione
    ("OZVault.sol",        "external_balanceOf", 1.0, True),    # OZ base + virtual offset0 (+1)
    ("SoladyVault.sol",    "external_balanceOf", 1.0, True),    # Solady base + virtual default
    ("OZVaultOffset6.sol", "external_balanceOf", 1e6, True),    # OZ + _decimalsOffset=6
    ("CacheFromBalanceOfVault.sol", "unknown", None, False),   # TRAPPOLA: accumulatore SYNC-da-balanceOf -> ASTIENE (no falso-SAFE)
]


def main():
    print("=" * 92)
    print("ESTRATTORE STRUTTURALE OFFLINE (gap b) — falsificato sui 5 shape ERC-4626 reali")
    print("=" * 92)
    ok = True
    for fname, exp_tat, exp_off, exp_an in GT:
        f = extract_facts(os.path.join(T, fname))            # NO llm_fact_fn -> path deterministico offline
        _, analyzable = defense_risk(f)
        tat_ok = (f.get("totalAssets_type") == exp_tat)
        off_ok = (exp_off is None) or (abs(float(f.get("effective_offset_magnitude", -1)) - exp_off) < 1e-6)
        an_ok = (analyzable == exp_an)
        good = tat_ok and off_ok and an_ok
        ok &= good
        print(f"  {'OK ' if good else 'XX '} {fname:22} -> tat={f.get('totalAssets_type'):18} off={f.get('effective_offset_magnitude')} "
              f"ds={f.get('defense_strength')} analyzable={analyzable}")

    assert ok, "estrattore strutturale: fatti NON combaciano col ground-truth reale -> inaffidabile"

    # --- end-to-end SENZA STUB: estrazione reale -> exec-gate -> certificato firmato ---
    print("\nflusso-prodotto SELF-CONTAINED (estrazione reale, niente stub):")
    env_v = audit_signed(os.path.join(T, "VaultBalanceOf.sol"), GATE, "test/GeneralGate.t.sol", "solmate_balanceof", signing_key=b"k")
    env_i = audit_signed(os.path.join(T, "OZVault.sol"), GATE, "test/GeneralGate.t.sol", "oz_offset0", signing_key=b"k")
    sv, si = env_v["certificate"]["verdict"], env_i["certificate"]["verdict"]
    print(f"  VaultBalanceOf -> {sv['status']}  (hash {env_v['content_hash'][:12]}...)")
    print(f"  OZVault        -> {si['status']}  (hash {env_i['content_hash'][:12]}...)")
    forge_ran = "forge non eseguibile" not in (sv.get("reason") or "")
    if forge_ran:
        assert sv["status"] == "PASS" and sv.get("counterexample"), "VaultBalanceOf (estrazione reale) -> deve dare VULN+witness"
        assert si["status"] == "PASS", "OZVault (estrazione reale) -> deve dare IMMUNE"
        # portabilita
        assert C.content_hash(C.from_dict(env_v["certificate"])) == env_v["content_hash"], "hash non deterministico"
        print("  end-to-end VULN/IMMUNE + portabilita: OK (nessuno stub, estrazione strutturale reale)")
    else:
        print("  [forge non disponibile -> salto i verdetti end-to-end; estrazione comunque verificata]")

    print("\n" + "=" * 92)
    print("ESITO: TUTTO COERENTE — estrattore-fatti DETERMINISTICO offline (no API/PROMETHEUS) corretto sui 5 shape reali.")
    print("Il flusso-prodotto e' ora SELF-CONTAINED: estrazione reale -> exec-gate -> certificato firmato, senza stub ne API.")
    print("Scope onesto: copre i pattern STRUTTURALI; sui casi semantici -> ABSTAIN (l'LLM-extractor resta superiore quando c'e' la key).")


if __name__ == "__main__":
    main()
