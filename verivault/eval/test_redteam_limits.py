"""
test_redteam_limits.py — CICLO 5 (RED-TEAM): il LIMITE ONESTO dell'universalita. Un null/limite eseguito vale come un L4.

TESI ATTACCATA: "il kernel di composizione e' universalmente utile". RED-TEAM: in un dominio SUB-additivo (ridondanza
N-replica con majority-vote) il guasto-di-sistema e' MOLTO PIU' BASSO del peggior singolo (la ridondanza AIUTA). Il
weakest-link/join (che prende il PEGGIORE) da' un bound SOUND (mai falso-SAFE) ma VACUAMENTE LASCO: non sa esprimere il
beneficio sub-additivo. -> l'universalita' della SOUNDNESS regge; l'universalita' della TIGHTNESS NO. Boundary onesto.

KILL-CONDITION (binaria, asserita):
  (1) SOUNDNESS preservata: il bound weakest-link (system_fail <= worst_single = P) e' un UPPER BOUND VALIDO (real <= P).
      Se fosse violato (real > bound) il kernel direbbe IMMUNE su un sistema fuori-budget = falso-SAFE -> tesi UCCISA.
  (2) LASCHEZZA reale: ratio = bound/real > 2x in modo riproducibile (esatto, binomiale) -> il limite esiste ed e' quantificato.
  (3) il kernel emette comunque IMMUNE (sound) col bound lasco -> dimostra 'agnostico != informativo'.
Esito atteso: la tesi-universale e' DELIMITATA (non uccisa): SOUND ovunque, TIGHT non in domini a ridondanza.
Riproducibile: `python eval/test_redteam_limits.py`  (stdlib; binomiale esatto, niente MC).
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from verivault.algebra import protocol_verdict
from verivault.reliability import binom_ge_k, reliability_bound

N, K, P, BUDGET = 3, 2, 0.08, 0.10   # 3 repliche, majority (guasto-sistema se >=2 falliscono), p=0.08 <= budget 0.10 -> ogni replica immune


def main():
    print("=" * 92)
    print(f"CICLO 5 RED-TEAM — limite in dominio SUB-additivo (ridondanza {N}-replica, majority>={K}, p={P}, budget={BUDGET})")
    print("=" * 92)

    # kernel: ogni replica immune (p<=budget), indipendente (monotone=True) -> protocol_verdict
    bounds = [reliability_bound(P, BUDGET, independent=True, source=f"replica{i}") for i in range(N)]
    verdict, b, sound = protocol_verdict(bounds)
    bound_rate = P                       # il bound weakest-link sul guasto-di-sistema = peggior singolo = P
    real_rate = binom_ge_k(N, P, K)      # guasto-di-sistema REALE (majority-vote, indipendenti): ESATTO
    ratio = bound_rate / real_rate if real_rate > 0 else float("inf")
    sound_ok = real_rate <= bound_rate + 1e-12

    print(f"kernel protocol_verdict (3 repliche, tutte entro budget): {verdict}  sound={sound}")
    print(f"bound weakest-link sul guasto-di-sistema  = {bound_rate:.5f}  (= peggior replica)")
    print(f"guasto-di-sistema REALE (majority, esatto) = {real_rate:.5f}  (la ridondanza ABBASSA il rischio)")
    print(f"SOUNDNESS (real <= bound, mai falso-SAFE):  {sound_ok}")
    print(f"LASCHEZZA ratio = bound/real = {ratio:.2f}x   (sound ma vacuamente conservativo)")

    # --- FALSIFICATORI IN-CODICE ---
    assert verdict == "IMMUNE" and sound, "il kernel dovrebbe certificare IMMUNE (tutte le repliche entro budget)"
    assert sound_ok, "SOUNDNESS VIOLATA: real > bound -> il kernel direbbe IMMUNE su sistema fuori-budget = falso-SAFE -> tesi UCCISA"
    assert ratio > 2.0, f"laschezza assente (ratio={ratio:.2f}x <= 2) -> nessun limite da riportare"

    print("\n" + "=" * 92)
    print("ESITO: tesi-universale DELIMITATA (non uccisa) — boundary ONESTO.")
    print(f"  SOUNDNESS e' universale: il weakest-link e' un upper bound VALIDO anche in dominio sub-additivo (real {real_rate:.4f} <= bound {bound_rate:.2f}).")
    print(f"  TIGHTNESS NON e' universale: in ridondanza il bound e' {ratio:.1f}x troppo lasco (non cattura il beneficio sub-additivo).")
    print("  => 'agnostico != informativo'. Brick futuro onesto: un operatore di composizione SUB-additivo-aware (oltre weakest-link)")
    print("     per i domini a ridondanza. Il REFUTE-gate e la non-falso-SAFE reggono ovunque; la STRETTEZZA del bound e' domain-specific.")


if __name__ == "__main__":
    main()
