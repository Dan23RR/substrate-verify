"""
conformal_gate.py — CALIBRAZIONE CONFORME PER-DISTRIBUZIONE con GARANZIA DI COPERTURA (il moat-calibrazione, reale).

Risponde a (eval/virgin_spotcheck.md):
  - Finding-1 (NEGATIVO): la SOGLIA-ASSOLUTA-congelata NON si trasferisce OOD (recall 0/2 al tie). Fix prescritto: conforme PER-DISTRIBUZIONE.
  - Finding-2 (POSITIVO): il SEGNALE generalizza (ranking recall@FP=0 = 1.0 OOD).

DISCIPLINA (anti-ASTRA, post-review): la garanzia conforme e' MARGINALE (mediata), non per-split. INOLTRE separo due
cose che un clamp ingenuo confondeva: (A) ACHIEVABILITY — a n piccolo la correzione finite-sample puo' non avere un
(1-eps)-quantile interno: in quel caso la soglia corretta e' +inf (ASTIENE), NON max(cal_safe) (che gonfierebbe l'FP
con un artefatto). (B) il mean FP/FN MISURATO solo sugli split ACHIEVABLE. Confronti STRICT (s > T_vuln). Scorer
UNIFICATO = lo stesso `defense_risk` spedito (coerenza BRICK 3). Riproducibile: `python eval/conformal_gate.py`.
"""
import json, os, math, sys, random, statistics

HERE = os.path.dirname(os.path.abspath(__file__))
ROWS = json.load(open(os.path.join(HERE, "data", "labeled_facts.json"), encoding="utf-8"))
N_SPLITS = 200

# scorer UNIFICATO: lo stesso defense_risk del prodotto (coerenza BRICK 3), con fallback self-contained FEDELE
# (riproduce l'early-return (0.5, False) dello spedito sui tat 'unknown' — fix review).
try:
    sys.path.insert(0, os.path.dirname(HERE))
    from verivault.stage2_score import defense_risk as _shipped_risk
    _RISK_SRC = "verivault.stage2_score.defense_risk (SHIPPED)"
except Exception:
    def _shipped_risk(f):
        tat = f.get("totalAssets_type")
        if tat not in ("internal_accounting", "external_balanceOf"):
            return 0.5, False
        ds = float(f.get("defense_strength", 0) or 0); risk = 1.0 - ds
        if tat == "internal_accounting":
            risk *= 0.2
        elif tat == "external_balanceOf":
            off = float(f.get("effective_offset_magnitude", 0) or 0)
            if not f.get("dead_shares") and off < 1e3:
                risk = max(risk, 0.85)
        return max(0.0, min(1.0, risk)), True
    _RISK_SRC = "fallback locale (fedele)"


def clean_risk(f):
    return _shipped_risk(f)[0]

def analyzable(f):
    return _shipped_risk(f)[1]

def q_upper(vals, eps):
    """(1-eps)-quantile conforme. Se l'indice finite-sample ESCE dal range -> +inf (ASTIENE), non clamp a max."""
    if not vals:
        return math.inf
    s = sorted(vals)
    raw = math.ceil((len(s) + 1) * (1 - eps)) - 1
    return math.inf if raw > len(s) - 1 else s[raw]      # niente clamp: overflow = soglia non raggiungibile

def q_lower(vals, eps):
    """eps-quantile conforme. Se l'indice esce sotto 0 -> -inf (ASTIENE sul lato SAFE)."""
    if not vals:
        return -math.inf
    s = sorted(vals)
    raw = math.ceil((len(s) + 1) * eps) - 1
    return -math.inf if raw < 0 else s[min(len(s) - 1, raw)]


def main():
    data = [(clean_risk(r["facts"]), r["label"]) for r in ROWS if analyzable(r["facts"])]
    n_v = sum(l for _, l in data); n_s = len(data) - n_v
    print("=" * 96)
    print(f"CONFORMAL GATE per-distribuzione — {len(data)} analizzabili ({n_v} VULN, {n_s} SAFE) · scorer={_RISK_SRC}")
    print(f"{N_SPLITS} split random 50/50 · GARANZIA MARGINALE (mean su split ACHIEVABLE) · soglia overflow -> +inf (astiene)")
    print("=" * 96)
    print(f"{'eps':>5} | {'achiev%':>8} {'mean_FP':>9} {'mean_FN':>9} {'mean_rec':>9} {'mean_abst':>9} | {'marginale':>10}")

    results = {}
    for eps in (0.05, 0.10, 0.20):
        fps, fns, recs, absts, n_ach, n_used = [], [], [], [], 0, 0
        for seed in range(N_SPLITS):
            rng = random.Random(seed); idx = list(range(len(data))); rng.shuffle(idx)
            h = len(idx) // 2
            cal = [data[i] for i in idx[:h]]; test = [data[i] for i in idx[h:]]
            cal_safe = [s for s, l in cal if l == 0]; cal_vuln = [s for s, l in cal if l == 1]
            tv = [s for s, l in test if l == 1]; ts = [s for s, l in test if l == 0]
            if not tv or not ts:
                continue
            n_used += 1
            T_vuln = q_upper(cal_safe, eps); T_safe = q_lower(cal_vuln, eps)
            if not math.isfinite(T_vuln):          # soglia VULN non raggiungibile a questo n -> split NON achievable
                continue
            n_ach += 1
            fp = sum(1 for s in ts if s > T_vuln) / len(ts)         # STRICT
            rec = sum(1 for s in tv if s > T_vuln) / len(tv)
            fn = sum(1 for s in tv if s < T_safe) / len(tv)         # T_safe=-inf -> 0 (astiene sul lato SAFE)
            abst = sum(1 for s, _ in test if T_safe <= s <= T_vuln) / len(test)
            fps.append(fp); recs.append(rec); fns.append(fn); absts.append(abst)
        ach = 100.0 * n_ach / max(1, n_used)
        if n_ach == 0:
            results[eps] = (ach, None, None, None, None, "IRRAGGIUNGIBILE")
            print(f"{eps:>5.2f} | {ach:>7.1f}% {'n/a':>9} {'n/a':>9} {'n/a':>9} {'n/a':>9} | {'IRRAGG.':>10}")
            continue
        mfp, mfn, mrec, mabst = (statistics.mean(x) for x in (fps, fns, recs, absts))
        marg = "OK" if (mfp <= eps + 1e-9 and mfn <= eps + 1e-9) else "VIOLATA"
        results[eps] = (ach, mfp, mfn, mrec, mabst, marg)
        print(f"{eps:>5.2f} | {ach:>7.1f}% {mfp:>9.3f} {mfn:>9.3f} {mrec:>9.3f} {mabst:>9.3f} | {marg:>10}")

    print("\nLETTURA ONESTA (post-review: niente clamp-artifact; achievability separata dall'overlap misurato):")
    print(" - achiev% = frazione di split con una soglia conforme FINITA. Se ~0 a eps=0.05, la garanzia e' IRRAGGIUNGIBILE")
    print("   a questo n (la correzione finite-sample astiene): NON e' 'FP misurato alto', e' 'non certificabile'.")
    print(" - Dove ACHIEVABLE, mean_FP/mean_FN sono la copertura marginale REALE. Se mean_FN>eps, i VULN colano nella")
    print("   banda-SAFE -> death-gate calibrazione FALLISCE comunque (serve piu' segnale/dati, non solo soglia).")
    print(" - La SOGLIA-ASSOLUTA-congelata FALLISCE OOD (virgin_spotcheck Finding-1). Lo SCORER e' un PRE-FILTRO/cost-router")
    print("   (NO-GO death-gate stretto, recall@FP=0=0.515); l'EXEC-GATE forge (L4) e' l'adjudicatore. Il segnale generalizza (Finding-2).")

    # VERDETTO MISURATO (onesto): separa irraggiungibilita' da violazione-di-overlap.
    print(f"\nVERDETTO CONFORME (misurato su {N_SPLITS} split):")
    for eps in (0.05, 0.10, 0.20):
        ach, mfp, mfn, mrec, mabst, marg = results[eps]
        if marg == "IRRAGGIUNGIBILE":
            print(f"  eps={eps:.2f}: IRRAGGIUNGIBILE a n_SAFE={n_s} (achiev={ach:.0f}%) -> la garanzia astiene, non e' falsificata da un FP gonfiato.")
        elif marg == "OK":
            print(f"  eps={eps:.2f}: garanzia marginale RISPETTATA (achiev={ach:.0f}%, mean_FP={mfp:.3f}, mean_FN={mfn:.3f}).")
        else:
            print(f"  eps={eps:.2f}: garanzia VIOLATA da OVERLAP reale (achiev={ach:.0f}%, mean_FP={mfp:.3f}, mean_FN={mfn:.3f}) -> serve piu' SEGNALE/DATI.")
    print(f"\nCONCLUSIONE (anti-ASTRA): a n_SAFE={n_s} la calibrazione-scorer NON e' un gate autonomo affidabile")
    print(f"  (eps bassi irraggiungibili; dove achievable, FN/overlap viola la garanzia). DATA NEEDED: SET VERGINE")
    print(f"  INDIPENDENTE (>=40-60 contratti, >=20 SAFE). exec-gate forge = adjudicatore sound (gap a aperto, onesto).")


if __name__ == "__main__":
    main()
