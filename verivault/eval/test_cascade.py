"""test_cascade.py — BRICK 3: la cascata T0->T1->T3 NON e' piu' dead-code; l'EXEC-GATE forge e' l'adjudicatore.
Verifica per ESECUZIONE (gira il forge interno ImmunityCert):
  (a) risk alto -> la cascata raggiunge T3 (forge) e adjudica -> PASS (certificato-immunita) sul modello OZ.
  (b) risk < 0.05 -> T0 si astiene CHEAP (conservativo: ABSTAIN, mai falso-SAFE), senza spendere forge.
Falsificatore in-codice (assert). Richiede forge (FORGE_BIN/PATH). Riproducibile: `python eval/test_cascade.py`."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from verivault import build_default_registry
from verivault.schemas import Claim, Status
from verivault.cascade import run_cascade


def _immunity_claim():
    return Claim(kind="erc4626.immunity",
                 payload={"test_path": "test/ImmunityCert.t.sol", "result_key": "oz:offset0"},
                 oracle="forge_gate", target="forge/test/ImmunityCert.t.sol")


def main():
    reg = build_default_registry()
    ok = True

    # (a) risk alto -> cascata fino a T3 (forge) -> il modello OZ-offset0 e' IMMUNE -> PASS
    v_hi = run_cascade(_immunity_claim(), reg, risk=0.9)
    print(f"(a) cascata risk=0.9 -> status={v_hi.status.value}  reason={v_hi.reason[:70]}")
    print(f"    script={v_hi.script}")
    ok &= (v_hi.status == Status.PASS)        # l'exec-gate ha adjudicato (immunita) via la cascata

    # (b) risk bassissimo -> T0 si astiene CHEAP (no forge), conservativo
    v_lo = run_cascade(_immunity_claim(), reg, risk=0.01)
    print(f"(b) cascata risk=0.01 -> status={v_lo.status.value}  reason={v_lo.reason[:70]}")
    ok &= (v_lo.status == Status.ABSTAIN and "T0" in v_lo.reason)

    # (c) FP=0 HARDENING (review): un claim di VULNERABILITA senza result_key NON deve dare VULN spuria
    #     (il blind-max su tutte le RESULT di ImmunityCert, dove 'raw'>0, generava un falso-positivo) -> ABSTAIN.
    spurious = Claim(kind="erc4626.donation_inflation",
                     payload={"test_path": "test/ImmunityCert.t.sol"},      # multi-RESULT, 'raw' profit>0
                     oracle="forge_gate", target="contratto_qualsiasi.sol")
    v_fp = run_cascade(spurious, reg, risk=0.9)
    print(f"(c) FP=0: claim senza result_key -> status={v_fp.status.value}  reason={v_fp.reason[:60]}")
    ok &= (v_fp.status == Status.ABSTAIN)        # NON PASS/VULN: niente blind-max su piu' RESULT

    print("\nESITO:", "TUTTO COERENTE" if ok else "INCOERENZA")
    assert ok, "cascata: routing T0/T3 o FP=0-hardening non rispettato"
    print("=> run_cascade NON e' piu' dead-code: T0 cost-routing + T3 exec-gate adjudica (BRICK 3, wirata in pipeline.audit).")


if __name__ == "__main__":
    main()
