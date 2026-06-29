"""
test_death_gate_runner.py — il RUNNER del death-gate gira OFFLINE end-to-end su contratti REALI (gap a, macchina).

Narrowing onesto del gap (a): il death-gate richiedeva l'estrazione-fatti (prima: API W5-v2 o PROMETHEUS_ROOT). Ora con
l'estrattore DETERMINISTICO offline (extract_solidity) la MACCHINA gira senza infra: estrai-fatti(reali) -> score ->
recall@FP=0 / AUC. L'UNICA parte ancora infra-gated e' la SCALA/INDIPENDENZA del dataset (>=40-60 contratti etichettati),
NON il codice. Qui lo provo sui 5 shape ERC-4626 reali (4 SAFE + 1 VULN), riusando le funzioni di death_gate.py.

KILL-CONDITION: se il runner non produce metriche su fatti REALI estratti offline -> la macchina non e' pronta.
SCOPE ONESTO: N=5 (suggestivo, non conclusivo, come virgin_spotcheck). Il numero NON e' il death-gate definitivo;
e' la prova che il RUNNER e' pronto e che il segnale separa (VULN sopra i SAFE) su codice reale estratto offline.
Riproducibile: `python eval/test_death_gate_runner.py`.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from verivault.stage1_extract import extract_facts

# import diretto dalle funzioni di death_gate (stesso file eval, caricato per path)
import importlib.util
_dg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "death_gate.py")
_spec = importlib.util.spec_from_file_location("death_gate", _dg_path)
_dg = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_dg)  # type: ignore

HERE = os.path.dirname(os.path.abspath(__file__))
STARTUP = os.path.dirname(os.path.dirname(HERE))
T = os.environ.get("GATE_DIR", os.path.join(STARTUP, "research_substrate_capacity", "exp", "virgin", "gate"))
T = os.path.join(T, "targets")

# manifest REALE locale (label a base strutturale documentata)
MANIFEST = [
    ("VaultBalanceOf.sol", 1),   # VULN: balanceOf raw, nessuna difesa
    ("VaultInternal.sol",  0),   # SAFE: accounting interno
    ("OZVault.sol",        0),   # SAFE: OZ virtual offset0
    ("SoladyVault.sol",    0),   # SAFE: Solady virtual
    ("OZVaultOffset6.sol", 0),   # SAFE: OZ offset6
]


def main():
    print("=" * 92)
    print("RUNNER death-gate OFFLINE end-to-end su 5 contratti ERC-4626 REALI (estrazione deterministica, no API)")
    print("=" * 92)
    rows = []
    for fname, label in MANIFEST:
        f = extract_facts(os.path.join(T, fname))         # estrazione DETERMINISTICA offline
        r = _dg.clean_risk(f)                              # stessa risk-fn spedita (defense_risk via fallback unificato)
        an = _dg.analyzable(f)
        rows.append((r, label, an, fname))
        print(f"  {fname:22} label={'VULN' if label else 'SAFE'}  risk={r:.3f}  analyzable={an}")

    data = [(r, l) for r, l, an, _ in rows if an]
    scores = [r for r, _ in data]; labels = [l for _, l in data]
    A = _dg.auc(scores, labels)
    rec = _dg.recall_at_fp0(scores, labels)
    print(f"\nMACCHINA del death-gate (su fatti reali estratti OFFLINE):  AUC={A:.3f}   recall@FP=0={rec:.3f}   (N={len(data)})")

    # FALSIFICATORI: il runner gira e produce metriche; il segnale separa (VULN sopra TUTTI i SAFE su questo set reale)
    assert len(data) == 5, "tutti e 5 i contratti reali devono essere analizzabili dall'estrattore offline"
    assert not (A != A), "AUC deve essere un numero (runner funzionante)"   # not NaN
    assert rec == 1.0, "su questo set reale il VULN (balanceOf) deve stare sopra tutti i SAFE (recall@FP=0=1.0)"

    print("\n" + "=" * 92)
    print("ESITO: TUTTO COERENTE — il RUNNER del death-gate gira OFFLINE su contratti reali (estrazione deterministica).")
    print("Narrowing onesto del gap (a): la MACCHINA e' pronta; resta infra-gated SOLO la SCALA/INDIPENDENZA del dataset")
    print("(>=40-60 contratti etichettati indipendenti). N=5 e' suggestivo (come virgin_spotcheck), non il death-gate definitivo.")


if __name__ == "__main__":
    main()
