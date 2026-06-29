"""
test_numerical_oracle.py — CICLO 3 (TEST): la meta'-ORACOLO del kernel e' DOMINIO-AGNOSTICA.

TESI (falsificabile): il disposer-con-witness del forge exec-gate (esegui -> trova l'input che rompe la proprieta' ->
witness ri-eseguito, FP=0) transferisce a un 3° dominio (stabilita floating-point), STESSA firma Oracle.decide->Verdict.
Il 'exploit' numerico = catastrophic cancellation della one-pass variance su dati a media grande.

KILL-CONDITION (binaria, asserita):
  (1) naive_var -> REFUTED con witness, e l'errore del witness e' DAVVERO > eps ri-verificato in esatto (Fraction): FP=0.
  (2) stable_var sugli STESSI input -> PASS (nessun witness): l'oracolo distingue algoritmo-rotto da algoritmo-sano.
  (3) search vuota -> ABSTAIN (mai finto-verdetto).
  (4) il witness e' RIPRODUCIBILE: ricalcolando naive(witness) l'errore-rel resta > eps (deterministico).
Riproducibile: `python eval/test_numerical_oracle.py`  (stdlib puro: fractions).
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from verivault.schemas import Claim, Status
from verivault.numerical import NumericalErrorOracle, ALGOS, rel_error

EPS = 0.01
# classe-input C: array a MEDIA GRANDE + spread piccolo (dove la cancellation morde). base oltre 2^53/3.
CANDIDATES = [
    [b + 1.0, b + 2.0, b + 3.0]
    for b in (1e7, 1e8, 1e9, 5e8, 3e9)
] + [[b + 0.5, b + 1.5, b + 2.5, b + 3.5] for b in (1e8, 2e9)]


def main():
    o = NumericalErrorOracle()
    print("=" * 92)
    print(f"CICLO 3 — 3° oracolo (numerico): exec-gate/witness su catastrophic cancellation (eps={EPS}, {len(CANDIDATES)} input)")
    print("=" * 92)

    v_naive = o.decide(Claim("numerical.var_accurate", {"algo": "naive_var", "eps": EPS, "candidates": CANDIDATES},
                             "numerical_error", "one-pass-variance"))
    v_stable = o.decide(Claim("numerical.var_accurate", {"algo": "stable_var", "eps": EPS, "candidates": CANDIDATES},
                              "numerical_error", "two-pass-variance"))
    v_empty = o.decide(Claim("numerical.var_accurate", {"algo": "naive_var", "eps": EPS, "candidates": []},
                             "numerical_error", "no-search"))

    print(f"naive_var (one-pass):  {v_naive.status.value}")
    if v_naive.counterexample:
        ce = v_naive.counterexample
        print(f"  witness_input={ce['witness_input']}  approx={ce['approx']:.6g}  exact={ce['exact']}  rel_error={ce['rel_error']:.3e}")
    print(f"stable_var (two-pass): {v_stable.status.value}  (max_rel_error_seen={ (v_stable.proof or {}).get('max_rel_error_seen', 'n/a'):.2e})")
    print(f"search vuota:          {v_empty.status.value}")

    # --- FALSIFICATORI IN-CODICE ---
    assert v_naive.status == Status.REFUTED and v_naive.counterexample, "naive_var deve essere REFUTED con witness (cancellation)"
    assert v_stable.status == Status.PASS, "stable_var deve essere PASS (nessun witness sugli stessi input)"
    assert v_empty.status == Status.ABSTAIN, "search vuota deve dare ABSTAIN (mai finto-verdetto)"

    # FP=0 / riproducibilita: ri-eseguo naive sul witness e ri-verifico in esatto che l'errore resta > eps
    w = v_naive.counterexample["witness_input"]
    f_naive, ref = ALGOS["naive_var"]
    re_check = float(rel_error(f_naive(w), ref(w)))
    print(f"\nFP=0 re-check: naive({w}) rel_error ricalcolato = {re_check:.3e} (eps={EPS}) -> {'> eps CONFERMATO' if re_check > EPS else 'FALLITO'}")
    assert re_check > EPS, "il witness NON e' riproducibile (errore ricalcolato <= eps) -> oracolo inaffidabile"

    print("\n" + "=" * 92)
    print("ESITO: TUTTO COERENTE — la meta'-ORACOLO (disposer con witness, FP=0) e' DOMINIO-AGNOSTICA.")
    print("3° dominio (floating-point) instanzia la STESSA firma Oracle.decide->Verdict del forge_gate (DeFi) e SlaOracle")
    print("(reliability). Il witness e' ri-verificato in aritmetica ESATTA, come il PoC forge e' ri-eseguito on-chain.")


if __name__ == "__main__":
    main()
