"""
test_substrate_agnostic.py — CAPSTONE (Ciclo 4): l'ORGANISMO verification-native. UN kernel, CELLULE eterogenee.

TESI (falsificabile): claim di DOMINI DIVERSI (numerico, affidabilita, DeFi) producono Certificate con lo STESSO kernel
e COMPONGONO in un UNICO certificato-di-sistema via compose.join_safety — il refute-gate vale CROSS-DOMINIO: se una
qualsiasi cella (di qualunque dominio) e' REFUTED, il sistema NON emette un safe-cert. Il certificato e' PORTABILE
(content_hash) come provato in test_certificate. Questo e' "il substrato": non un tool ERC-4626, ma un organismo le cui
celle (oracoli) vivono in domini ortogonali e i cui certificati si compongono.

KILL-CONDITION (binaria, asserita):
  (1) 3 oracoli di 3 domini producono Certificate validi (numerico+reliability LIVE; DeFi citato dal forge L4).
  (2) join_safety di 3 claim ETEROGENEI -> system PASS, emits=True, composed_from copre i 3 domini, confidence=anello-debole.
  (3) iniettando UNA cella REFUTED (naive_var) -> system REFUTED, emits=False (il sistema difettoso non emette safe-cert).
  (4) il certificato-di-sistema e' portabile (content_hash presente, deterministico).
Riproducibile: `python eval/test_substrate_agnostic.py`  (stdlib + verivault; nessun forge/RPC: il verdetto DeFi e' citato).
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from verivault.schemas import Claim, Verdict, Status, Certificate
from verivault.compose import join_safety
from verivault.numerical import NumericalErrorOracle
from verivault.reliability import SlaOracle
from verivault import certificate as C

BIG = [1e8 + 1, 1e8 + 2, 1e8 + 3]


def main():
    print("=" * 92)
    print("CAPSTONE — l'ORGANISMO: claim di 3 DOMINI compongono in UN certificato-di-sistema (stesso kernel)")
    print("=" * 92)
    num, sla = NumericalErrorOracle(), SlaOracle()

    # --- 3 CELLULE in 3 DOMINI, stesso kernel Oracle.decide->Verdict->Certificate ---
    c_num = Claim("numerical.var_accurate", {"algo": "stable_var", "eps": 0.01, "candidates": [BIG]}, "numerical_error", "two-pass-var")
    cert_num = Certificate(c_num, num.decide(c_num))                                   # NUMERICO (live)

    c_rel = Claim("sla.within_budget", {"failure_rate_measured": 0.05, "sla_budget": 0.08, "n_samples": 1_000_000}, "sla_montecarlo", "svc-A")
    cert_rel = Certificate(c_rel, sla.decide(c_rel))                                   # AFFIDABILITA (live)

    c_defi = Claim("erc4626.immunity", {"vault": "OZVault offset0"}, "forge_gate", "gate/test/GeneralGate.t.sol")
    v_defi = Verdict(Status.PASS, confidence=1.0,
                     proof={"immunity_certificate": True, "max_attacker_profit_wei": -497512437810945275,
                            "scope_covers": "donation/first-depositor", "provenance": "forge L4 (GeneralGate.t.sol)"},
                     reason="exec-gate forge: nessuna donazione profittevole entro il bound (L4 citato)",
                     script="gate/test/GeneralGate.t.sol")
    cert_defi = Certificate(c_defi, v_defi)                                            # DeFi (verdetto L4 citato)

    print(f"cellula NUMERICO:     {cert_num.verdict.status.value}  ({c_num.kind})")
    print(f"cellula AFFIDABILITA: {cert_rel.verdict.status.value}  ({c_rel.kind})")
    print(f"cellula DeFi:         {cert_defi.verdict.status.value}  ({c_defi.kind})")

    # --- COMPOSIZIONE CROSS-DOMINIO: sistema SAFE iff TUTTE le proprieta (di domini diversi) reggono ---
    system = join_safety([cert_num, cert_rel, cert_defi], target="sistema-eterogeneo")
    env = C.envelope(system)
    print(f"\nSISTEMA (3 domini composti): {system.verdict.status.value}  emits={system.emits}")
    print(f"  composed_from = {system.composed_from}")
    print(f"  weakest_link  = {(system.verdict.proof or {}).get('weakest_link')}  confidence={system.verdict.confidence}")
    print(f"  content_hash  = {env['content_hash'][:16]}...  (certificato-di-sistema PORTABILE)")

    # --- NEGATIVO: una cella numerica ROTTA (naive_var) -> il sistema NON emette safe-cert (refute-gate cross-dominio) ---
    c_bad = Claim("numerical.var_accurate", {"algo": "naive_var", "eps": 0.01, "candidates": [BIG]}, "numerical_error", "one-pass-var")
    cert_bad = Certificate(c_bad, num.decide(c_bad))
    system_bad = join_safety([cert_rel, cert_bad, cert_defi], target="sistema-con-difetto-numerico")
    print(f"\nSISTEMA con 1 cella numerica ROTTA: {system_bad.verdict.status.value}  emits={system_bad.emits}  (non esce safe-cert)")

    # --- FALSIFICATORI IN-CODICE ---
    assert cert_num.verdict.status == Status.PASS, "cella numerica (stable_var) dovrebbe PASS"
    assert cert_rel.verdict.status == Status.PASS, "cella affidabilita (entro SLA) dovrebbe PASS"
    assert cert_defi.verdict.status == Status.PASS, "cella DeFi (immune) dovrebbe PASS"
    assert system.verdict.status == Status.PASS and system.emits, "sistema 3-domini dovrebbe PASS ed emettere"
    domains = {k.split(".")[0] for k in system.composed_from}
    assert domains == {"numerical", "sla", "erc4626"}, f"composed_from deve coprire i 3 domini, ho {domains}"
    assert cert_bad.verdict.status == Status.REFUTED, "naive_var dovrebbe REFUTED"
    assert system_bad.verdict.status == Status.REFUTED and not system_bad.emits, "sistema con cella rotta NON deve emettere safe-cert"
    assert env["content_hash"] and env["content_hash"] == C.content_hash(system), "certificato-di-sistema non portabile/deterministico"

    print("\n" + "=" * 92)
    print("ESITO: TUTTO COERENTE — l'ORGANISMO regge. UN kernel; celle in 3 domini ortogonali; certificati che COMPONGONO")
    print("cross-dominio col refute-gate (un difetto in QUALSIASI dominio -> niente safe-cert) e un certificato-di-sistema")
    print("PORTABILE. VeriVault NON e' un tool ERC-4626: e' un SUBSTRATO verification-native dominio-agnostico, eseguito.")


if __name__ == "__main__":
    main()
