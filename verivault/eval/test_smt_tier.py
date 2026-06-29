"""
test_smt_tier.py — FALSIFICAZIONE del tier T1 (SMT continuo) vs grid-9-punti.
Domande binarie:
  (1) SOUNDNESS: il witness D* di z3 e' REALE? (attack_profit(D*) > 0 nell'aritmetica forge-identica)
  (2) RECALL-GAIN: esistono casi dove il grid-9-punti dice IMMUNE ma SMT/ground-truth-densa dice EXPLOITABLE?
      (= l'SMT chiude i falsi-negativi TRA i punti-griglia). Se NO -> il tier e' numerologia -> taglialo.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from verivault.oracles.smt_rounding import synthesize


def attack_profit(O, V, D, raw):
    """aritmetica floor IDENTICA a forge/test/ImmunityCert.t.sol (ground-truth)."""
    if raw:
        A = 1 + D
        sv = (V * 1) // A
        S = 1 + sv; A = A + V
        got = (1 * A) // S
        return got - 1 - D
    else:
        A = 1 + D
        sv = (V * 2 * O) // (D + 2)
        S = O + sv; A = A + V
        got = (O * (D + V + 2)) // (S + O)
        return got - 1 - D


def grid9(V):
    return [0, V // 2, V, 2 * V, 3 * V, 5 * V, 10 * V, 50 * V, 100 * V]


def dense_exploitable(O, V, k, raw, n=4000):
    hi = k * V
    step = max(1, hi // n)
    best = -1 << 200; bestD = 0
    for D in range(0, hi + 1, step):
        p = attack_profit(O, V, D, raw)
        if p > best:
            best = p; bestD = D
    return best > 0, best, bestD


def main():
    print(f"{'pattern':14} {'O':4} {'V':>10} | {'grid9':8} {'SMT':10} {'dense_GT':10} | flag")
    sound_ok = True; recall_gain = 0; smt_unsound_miss = 0; rows = 0
    Vs = [1, 2, 5, 10, 100, 1000, 10**6, 10**9, 10**18]
    cfgs = [("RAW", 0, True)] + [(f"OZ_o{o}", 10 ** o, False) for o in (0, 1, 2, 3, 4, 6)]
    for V in Vs:
        for name, O, raw in cfgs:
            k = 100
            Oeff = O if O > 0 else 1
            gmax = max(attack_profit(Oeff, V, D, raw) for D in grid9(V))
            grid_expl = gmax > 0
            st, w = synthesize(Oeff, V, k, raw=raw)
            smt_expl = (st == "SAT")
            gt_expl, gt_best, gt_D = dense_exploitable(Oeff, V, k, raw)
            # soundness del witness
            if smt_expl:
                if attack_profit(Oeff, V, w, raw) <= 0:
                    sound_ok = False; flag = "<<UNSOUND witness!"
                else:
                    flag = ""
            else:
                flag = ""
            # SMT manca un exploit reale? (deve combaciare con ground-truth)
            if (not smt_expl) and gt_expl:
                smt_unsound_miss += 1; flag += " SMT-misses-GT"
            # RECALL GAIN: grid immune ma (smt|gt) exploitable
            if (not grid_expl) and (smt_expl or gt_expl):
                recall_gain += 1; flag += " <-RECALL-GAIN(grid misses)"
            rows += 1
            print(f"{name:14} {O if O else 0:<4} {V:>10} | {str(grid_expl):8} {('SAT D*='+str(w)) if smt_expl else 'UNSAT':10} {str(gt_expl):10} | {flag}")
    print("\n" + "=" * 70)
    print(f"casi totali: {rows}")
    print(f"(1) SOUNDNESS witness z3 (D* reale in forge-arit): {'OK' if sound_ok else 'FALLITA'}")
    print(f"    SMT manca exploit reali (gt SAT, smt UNSAT): {smt_unsound_miss} (deve essere 0)")
    print(f"(2) RECALL-GAIN (grid IMMUNE ma exploit reale esiste): {recall_gain} casi")
    if sound_ok and smt_unsound_miss == 0 and recall_gain > 0:
        print(">>> T1 VALIDATO: witness sound + SMT chiude falsi-negativi che il grid-9pt manca (recall reale) <<<")
    elif sound_ok and smt_unsound_miss == 0:
        print(">>> T1 SOUND ma 0 recall-gain su questo sweep: il grid-9pt e' gia sufficiente qui -> "
              "l'edge SMT e' la PROVA-SU-CONTINUO (immunita certificata), non recall extra. Onesto. <<<")
    else:
        print(">>> T1 PROBLEMA (unsound o miss) -> NON wirare finche non e' sound <<<")


if __name__ == "__main__":
    main()
