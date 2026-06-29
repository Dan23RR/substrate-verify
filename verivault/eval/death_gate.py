"""
death_gate.py — IL CANCELLO PRE-REGISTRATO, ESEGUIBILE (non piu un TODO).

Risponde alla critica "metriche autodichiarate / dataset TODO": self-contained, gira sul dataset REALE bundlato
(eval/data/labeled_facts.json, 68 contratti share-accounting con fatti LLM-estratti) e PRODUCE il numero.
Riproducibile: `python eval/death_gate.py`  (oppure `python eval/death_gate.py <manifest.json> <labels.json>` su set esterno).

ONESTA: lo SCORER (Stadio 1+2) e un PRE-FILTRO cheap; il MOAT verificabile e l'exec-gate forge
(exp/virgin/gate/*.t.sol, `forge test`). Qui misuriamo SOLO il potere discriminante dello scorer.
CONDIZIONE PRE-REGISTRATA (prereg.md): GO se recall@FP=0 (ranking) > 0.636 E AUC > 0.75.
CAVEAT: held-out IN-DISTRIBUTION (stesso set da 68). Sul set VERGINE indipendente (exp/virgin/) la
soglia-assoluta-congelata NON si trasferisce (recall 0/2 OOD) -> serve ricalibrazione conforme per-distribuzione.
"""
from __future__ import annotations
import sys, json, os, random, statistics

HERE = os.path.dirname(os.path.abspath(__file__))
BASELINE = 0.636


# BRICK 3: il death-gate misura lo SCORER SPEDITO (verivault.stage2_score.defense_risk), non una copia.
# Prima `clean_risk` locale divergeva da `defense_risk` del prodotto su 24/68 righe (mancava il bump
# external_balanceOf+offset<1e3 -> max(risk,0.85)). Ora UNA sola risk-fn: il gate certifica cio che spedisci.
try:
    sys.path.insert(0, os.path.dirname(HERE))
    from verivault.stage2_score import defense_risk as _shipped_risk   # (risk, analyzable)
    _RISK_SRC = "verivault.stage2_score.defense_risk (SHIPPED)"
except Exception:                                  # fallback self-contained (se il package non importa)
    def _shipped_risk(facts):
        tat = facts.get("totalAssets_type")
        if tat not in ("internal_accounting", "external_balanceOf"):
            return 0.5, False                  # fedele allo spedito (stage2_score:20-21): unknown -> (0.5, False)
        ds = float(facts.get("defense_strength", 0) or 0); risk = 1.0 - ds
        if tat == "internal_accounting":
            risk *= 0.2
        elif tat == "external_balanceOf":
            off = float(facts.get("effective_offset_magnitude", 0) or 0)
            if not facts.get("dead_shares") and off < 1e3:
                risk = max(risk, 0.85)
        return max(0.0, min(1.0, risk)), True
    _RISK_SRC = "fallback locale (package non importabile)"


def clean_risk(facts):
    return _shipped_risk(facts)[0]


def analyzable(facts):
    return _shipped_risk(facts)[1]


def auc(scores, labels):
    pos = [s for s, l in zip(scores, labels) if l == 1]
    neg = [s for s, l in zip(scores, labels) if l == 0]
    if not pos or not neg:
        return float("nan")
    return sum((1.0 if p > n else 0.5 if p == n else 0.0) for p in pos for n in neg) / (len(pos) * len(neg))


def recall_at_fp0(scores, labels):
    pos = [s for s, l in zip(scores, labels) if l == 1]
    neg = [s for s, l in zip(scores, labels) if l == 0]
    if not pos or not neg:
        return float("nan")
    return sum(1 for p in pos if p > max(neg)) / len(pos)


def load_rows():
    """default: dataset reale bundlato; oppure manifest+labels esterni (extract_facts on-the-fly)."""
    if len(sys.argv) >= 3:
        sys.path.insert(0, os.path.dirname(HERE))
        from verivault.stage1_extract import extract_facts
        manifest = json.load(open(sys.argv[1])); labels = json.load(open(sys.argv[2]))
        out = []
        for c in manifest:
            f = extract_facts(c["path"])
            lab = labels.get(c["id"])
            if lab is not None:
                out.append((clean_risk(f), 1 if lab == "VULNERABLE" else 0, analyzable(f)))
        return out, "ESTERNO (" + sys.argv[1] + ")"
    rows = json.load(open(os.path.join(HERE, "data", "labeled_facts.json"), encoding="utf-8"))
    return [(clean_risk(r["facts"]), r["label"], analyzable(r["facts"])) for r in rows], "BUNDLATO (eval/data/labeled_facts.json)"


def main():
    allrows, src = load_rows()
    data = [(s, l) for s, l, an in allrows if an]
    scores = [s for s, _ in data]; labels = [l for _, l in data]
    n_v = sum(labels); n_s = len(labels) - n_v
    print("=" * 80)
    print(f"DEATH-GATE eseguibile — dataset {src}")
    print(f"{len(allrows)} totali, {len(data)} analizzabili: {n_v} VULN, {n_s} SAFE (astensione onesta su unknown)")
    print("=" * 80)

    A = auc(scores, labels); rank_full = recall_at_fp0(scores, labels)
    print(f"AUC (in-distribution):                  {A:.3f}")
    print(f"recall@FP=0 ranking (in-distribution):  {rank_full:.3f}")

    rec_fr, fp_fr, rank_te = [], [], []
    for seed in range(5):
        rng = random.Random(seed); idx = list(range(len(data))); rng.shuffle(idx)
        half = len(idx) // 2
        cal = [data[i] for i in idx[:half]]; test = [data[i] for i in idx[half:]]
        cal_safe = [s for s, l in cal if l == 0]
        T = max(cal_safe) if cal_safe else 1.0
        tv = [s for s, l in test if l == 1]; ts = [s for s, l in test if l == 0]
        if tv: rec_fr.append(sum(1 for s in tv if s > T) / len(tv))
        if tv and ts: fp_fr.append(sum(1 for s in ts if s > T) / len(ts))
        rank_te.append(recall_at_fp0([s for s, l in test], [l for s, l in test]))
    print(f"\nheld-out (5 split, soglia CONGELATA su calibration-SAFE):")
    print(f"  recall@soglia-congelata = {statistics.mean(rec_fr):.3f}  FP-rate = {statistics.mean(fp_fr):.3f}")
    print(f"  recall@FP=0 ranking (test) = {statistics.mean(rank_te):.3f}")

    go = (rank_full > BASELINE) and (A > 0.75)
    print("\n" + "-" * 80)
    print(f"PRE-REGISTRATA: recall@FP=0 > {BASELINE} AND AUC > 0.75  ->  {'GO' if go else 'NO-GO'} (in-distribution)")
    print("CAVEAT ONESTO: held-out IN-DISTRIBUTION, non set vergine. Sul vergine la soglia-congelata NON")
    print("si trasferisce (recall 0/2). Lo scorer e un pre-filtro; il MOAT verificabile e l'exec-gate forge.")


if __name__ == "__main__":
    main()
