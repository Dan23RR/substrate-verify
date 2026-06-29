"""
death_gate_w5v2.py — DEATH-GATE a N maggiore con estrazione W5-v2 (sub-agent LLM) su shape reali execution-labeled (gap a).

Avanza il death-gate da N=5 (test_death_gate_runner, deterministico) a N=9 con i fatti estratti dall'ESTRATTORE SEMANTICO
W5-v2 (sub-agenti, nessuna API-key; bundlati in eval/data/w5v2_facts_9.json come provenance) e label OGGETTIVE per ESECUZIONE
(exec-gate forge: VULN se profit>0). Caso discriminante: OZ v4.8 (pre-virtual-shares) — W5-v2 l'ha colto (defense 0.05).

CONDIZIONE PRE-REGISTRATA (prereg.md): GO se recall@FP=0 > 0.636 AND AUC > 0.75.
CAVEAT ONESTO (scope-naming, anti-ASTRA):
  - N=9 (3 VULN / 6 SAFE): SUGGESTIVO, non conclusivo (il death-gate definitivo richiede >=40-60, >=20 SAFE, third-party).
  - Shape PATTERN-DIVERSE ma SEMI-SINTETICHE (wrapper scritti per il gate su librerie reali); NON un corpus deployato terzo.
  - recall@FP=0 resta FRAGILE all'outlier-SAFE (come il 68-set in-distribution: un SAFE alto cappa la metrica -> NO-GO la').
Riproducibile: `python eval/death_gate_w5v2.py`.
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from verivault.stage2_score import defense_risk

HERE = os.path.dirname(os.path.abspath(__file__))
ROWS = json.load(open(os.path.join(HERE, "data", "w5v2_facts_9.json"), encoding="utf-8"))
BASELINE = 0.636


def auc(scores, labels):
    pos = [s for s, l in zip(scores, labels) if l == 1]; neg = [s for s, l in zip(scores, labels) if l == 0]
    if not pos or not neg:
        return float("nan")
    return sum((1.0 if p > n else 0.5 if p == n else 0.0) for p in pos for n in neg) / (len(pos) * len(neg))


def recall_at_fp0(scores, labels):
    pos = [s for s, l in zip(scores, labels) if l == 1]; neg = [s for s, l in zip(scores, labels) if l == 0]
    if not pos or not neg:
        return float("nan")
    return sum(1 for p in pos if p > max(neg)) / len(pos)


def main():
    print("=" * 96)
    print(f"DEATH-GATE W5-v2 (sub-agent extraction) — N={len(ROWS)} shape reali execution-labeled (gap a, N maggiore)")
    print("=" * 96)
    rows = []
    for r in ROWS:
        risk, an = defense_risk(r)
        rows.append((risk, r["label"], an, r["name"]))
        print(f"  {r['name']:18} ds={r['defense_strength']:.2f} off={r['effective_offset_magnitude']:>8} "
              f"-> risk={risk:.3f}  label={'VULN' if r['label'] else 'SAFE'}  analyzable={an}")
    data = [(s, l) for s, l, an, _ in rows if an]
    scores = [s for s, _ in data]; labels = [l for _, l in data]
    n_v = sum(labels); n_s = len(labels) - n_v
    A = auc(scores, labels); rec = recall_at_fp0(scores, labels)
    max_safe = max([s for s, l in data if l == 0], default=0.0)
    min_vuln = min([s for s, l in data if l == 1], default=0.0)
    margin = min_vuln - max_safe
    go = (rec > BASELINE) and (A > 0.75)

    print(f"\nN analizzabili={len(data)} ({n_v} VULN, {n_s} SAFE)")
    print(f"AUC = {A:.3f}    recall@FP=0 = {rec:.3f}    (max_SAFE_risk={max_safe:.3f}, min_VULN_risk={min_vuln:.3f}, margine FP=0 = {margin:+.3f})")
    print(f"PRE-REGISTRATA: recall@FP=0 > {BASELINE} AND AUC > 0.75  ->  {'GO' if go else 'NO-GO'}")
    print("\nCAVEAT ONESTO: N=9 suggestivo (non i >=40-60 third-party del death-gate definitivo); shape semi-sintetiche su")
    print(f"librerie reali; margine FP=0 SOTTILE ({margin:+.3f}, guidato dai virtual-offset0 SAFE a 0.85 = cautela dello scorer).")
    print("Il SEGNALE separa (ranking), ma recall@FP=0 resta ostaggio dell'outlier-SAFE (il 68-set in-distribution dava NO-GO).")
    print("Discriminante: W5-v2 ha colto OZ v4.8 come VULN (defense 0.05), non ingannato dal nome OZ.")

    # FALSIFICATORE: su questo set, il GO pre-registrato deve reggere (recall>0.636 AND AUC>0.75); altrimenti NO-GO onesto.
    assert go, f"NO-GO su N=9: recall@FP=0={rec:.3f} / AUC={A:.3f} (lo scorer non separa su questo set reale)"
    print("\nESITO: GO su N=9 (W5-v2, execution-labeled) — suggestivo-positivo, con i caveat sopra. SCALA + corpus terzo = pilastro restante.")


if __name__ == "__main__":
    main()
