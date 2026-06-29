"""test_algebra.py — FALSIFICAZIONE anti-ASTRA dell'algebra di composizione (testo il mio stesso moat).
(1) soundness: [immune, vuln] -> JOIN eredita il vuln. (2) monotonia. (3) KILL: weakest-link si ROMPE sotto
coupling super-additivo (oracle-leverage), e l'algebra DEVE declassare a triage (ABSTAIN), non emettere falso-IMMUNE.
Onesto: il MEV composto qui e MODELLATO (deterministico); il test coupled-FORGE su fork reale e il gate successivo."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from verivault.algebra import EconomicBound, protocol_verdict

WEI = 10**18

def composed_mev_oracle_leverage(V, pump_factor, ltv):
    """modello deterministico di un exploit COMPOSTO (A price-oracle di B, leva):
    l'attaccante posta collaterale di valore V in A, flash-pompa A.price di pump_factor, prende a prestito
    ltv*(V*pump_factor) da B alla valutazione gonfiata, A.price torna giu -> abbandona il prestito.
    profitto = prestito - collaterale-perso."""
    borrowed = int(ltv * V * pump_factor)
    return borrowed - V

def main():
    print("=" * 84)
    print("FALSIFICAZIONE anti-ASTRA — algebra di composizione (weakest-link)")
    print("=" * 84)
    ok = True

    # (1) SOUNDNESS: una catena con un link bucato non puo essere certificata safe
    v1, _, _ = protocol_verdict([EconomicBound(-1, 100, True, "A_immune"),
                                 EconomicBound(100 * WEI, 100, True, "B_vuln")])
    print(f"(1) SOUNDNESS  [immune, vuln] -> {v1}   (JOIN eredita il link bucato)")
    ok &= (v1 == "VULN")

    # (2) MONOTONIA: rimosso il link debole, il composto puo solo migliorare
    v2, _, _ = protocol_verdict([EconomicBound(-1, 100, True, "A_immune"),
                                 EconomicBound(-2, 100, True, "C_immune")])
    print(f"(2) MONOTONIA  [immune, immune isolati] -> {v2}")
    ok &= (v2 == "IMMUNE")

    # (3) KILL anti-ASTRA: coupling super-additivo rompe weakest-link
    V = 100 * WEI
    mev_A, mev_B = -1, -1                                   # entrambi per-contract IMMUNI (profit diretto <=0)
    mev_comp = composed_mev_oracle_leverage(V, pump_factor=2.0, ltv=0.9)   # 0.8V > 0
    holds = mev_comp <= max(mev_A, mev_B)
    print(f"\n(3) KILL-CONDITION (oracle-leverage coupling):")
    print(f"    MEV_A={mev_A}  MEV_B={mev_B}  ->  MEV(A.B) modellato = {mev_comp/WEI:+.1f} token")
    print(f"    weakest-link  MEV(A.B) <= max(MEV_A,MEV_B)?  ->  {'REGGE' if holds else 'ROTTA'}")
    ok &= (not holds)                                       # ATTESO: si rompe sotto coupling

    # l'algebra DEVE rifiutare di certificare safe il protocollo coupled (A non-monotono -> ABSTAIN, non IMMUNE)
    v3, b3, sound3 = protocol_verdict([EconomicBound(mev_A, 100, monotone=False, source="A_price_coupled"),
                                       EconomicBound(mev_B, 100, monotone=True, source="B")])
    print(f"    protocol_verdict (A non-monotono) = {v3}  | sound={sound3}   (declassato a TRIAGE, non falso-IMMUNE)")
    ok &= (v3 == "ABSTAIN" and not sound3)

    # prova che il gate-monotono e LOAD-BEARING: marcando A (erroneamente) monotono -> IMMUNE falso
    v_wrong, _, _ = protocol_verdict([EconomicBound(mev_A, 100, True, "A_wrong"),
                                      EconomicBound(mev_B, 100, True, "B")])
    print(f"    se A fosse (a torto) marcato monotono -> {v_wrong}  = FALSO-SAFE (l'exploit composto esiste)")
    print(f"    => il gate-monotono e LOAD-BEARING: e cio che separa prova-sound da triage.")

    # (4) DERIVAZIONE STRUTTURALE di `monotone` (BRICK 5b): non hand-set, ma dalla dipendenza-oracolo-esterno,
    #     giustificata EMPIRICAMENTE da gate/test/{Coupled,OracleCoupled}Gate.t.sol (eseguiti).
    from verivault.algebra import monotone_from_dependency
    mono_iso = monotone_from_dependency(external_flash_oracle=False)   # vault-interno (CoupledGate: REGGE)
    mono_dep = monotone_from_dependency(external_flash_oracle=True)    # legge spot-AMM (OracleCoupledGate: +78e21)
    v4, _, sound4 = protocol_verdict([EconomicBound(-1, 100, mono_iso, "vault_isolated"),
                                      EconomicBound(-1, 100, mono_dep, "lend_on_amm_oracle")])
    print(f"\n(4) DERIV monotone strutturale: iso={mono_iso} dep={mono_dep} -> protocol_verdict={v4} sound={sound4}")
    print(f"    (due link singolarmente immuni, ma uno dipende da oracolo-esterno-manipolabile -> ABSTAIN, mai falso-IMMUNE)")
    ok &= (mono_iso is True and mono_dep is False and v4 == "ABSTAIN" and not sound4)

    print("\n" + "=" * 84)
    print(f"ESITO: {'TUTTO COERENTE' if ok else 'INCOERENZA'}")
    print("VERDETTO ONESTO: weakest-link e SOUND solo per link fund-flow-ISOLATI (monotoni). Sotto coupling")
    print("super-additivo (oracolo condiviso, reentrancy cross-vault, flash-loan) si DECLASSA a triage (ABSTAIN).")
    print("Il moat-composizione e dichiarato col suo limite, MAI gonfiato. [Next gate: coupled-FORGE su fork reale.]")
    assert ok, "falsificazione incoerente"

if __name__ == "__main__":
    main()
