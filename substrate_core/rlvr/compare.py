"""substrate_core.rlvr.compare — il CONFRONTO del cancello §8 sui report dei bracket (gira ovunque, no-GPU).

Legge gli eval_report.json prodotti su Colab (uno per bracket-seed) e calcola i delta che decidono la tesi:
  - A_control            = baseline forte (SFT)
  - B_plain_dpo          = DPO senza witness
  - B_witness_dpo        = DPO con witness
  EFFETTO-WITNESS PURO = media(B_witness) - media(B_plain)  su seed appaiati  <- LA TESI (red-team: ~2 bit/REFUTED)
  SFT-vs-DPO            = media(B_*) - media(A_control)                          <- confound, solo informativo

Vincolo duro su OGNI bracket: false_proven == 0 (peccato cardinale). Soglia tesi: effetto-witness >= 5pp
sul solve-rate-genuino, su >=3 seed, con calibrazione (abstain_recall/aurc) non-peggiore. Ogni numero qui
cita gli eval_report.json che l'hanno prodotto (path stampati).
"""
from __future__ import annotations

import glob
import json
import os
from typing import Any, Dict, List, Optional

DEATH_THRESHOLD_PP = 5.0
BRACKETS = ("A_control", "B_plain_dpo", "B_witness_dpo")


def _mean(xs: List[float]) -> Optional[float]:
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def summarize(reports: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggrega per bracket (media sui seed) e calcola i delta del cancello. reports = lista di eval_report dict."""
    by: Dict[str, List[Dict[str, Any]]] = {b: [] for b in BRACKETS}
    for r in reports:
        b = r.get("bracket")
        if b in by:
            by[b].append(r)
    agg: Dict[str, Any] = {}
    for b, rs in by.items():
        if not rs:
            agg[b] = None
            continue
        agg[b] = {
            "n_seeds": len(rs),
            "solve_rate": _mean([r.get("solve_rate_genuino") for r in rs]),
            "abstain_recall": _mean([r.get("abstain_recall") for r in rs]),
            "aurc": _mean([(r.get("risk_coverage") or {}).get("aurc") for r in rs]),
            "false_proven_total": sum(r.get("false_proven_count", 0) for r in rs),
            "seeds": sorted(r.get("seed") for r in rs if r.get("seed") is not None),
        }

    def _delta(x, y, key):
        if agg.get(x) and agg.get(y) and agg[x][key] is not None and agg[y][key] is not None:
            return round(100.0 * (agg[x][key] - agg[y][key]), 2)   # in punti percentuali
        return None

    witness_effect_pp = _delta("B_witness_dpo", "B_plain_dpo", "solve_rate")
    sft_vs_dpo_pp = _delta("B_witness_dpo", "A_control", "solve_rate")
    any_false_proven = any((agg.get(b) or {}).get("false_proven_total", 0) > 0 for b in BRACKETS)
    diffs = sorted({r.get("difficulty") for r in reports if r.get("difficulty") is not None})
    if len(diffs) > 1:
        print(f"  ATTENZIONE: difficolta' MISCHIATE {diffs} -> confronto non valido. Filtra con --difficulty.")

    thesis = None
    if witness_effect_pp is not None:
        thesis = (witness_effect_pp >= DEATH_THRESHOLD_PP) and not any_false_proven
    return {
        "per_bracket": agg,
        "witness_effect_pp": witness_effect_pp,           # B_witness - B_plain (LA TESI)
        "witness_abstain_delta_pp": _delta("B_witness_dpo", "B_plain_dpo", "abstain_recall"),
        "sft_vs_dpo_pp": sft_vs_dpo_pp,                    # informativo (confound)
        "any_false_proven": any_false_proven,             # VINCOLO DURO -> deve essere False
        "death_threshold_pp": DEATH_THRESHOLD_PP,
        "difficulties_present": diffs,
        "thesis_supported": thesis,   # None se mancano i bracket B; True/False altrimenti
    }


def load_reports(root: str, difficulty: Optional[int] = None, data: Optional[str] = None) -> List[Dict[str, Any]]:
    out = []
    for path in glob.glob(os.path.join(root, "*", "eval_report.json")):
        try:
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
            if difficulty is not None and d.get("difficulty") != difficulty:
                continue
            if data is not None and d.get("data", "synthetic") != data:
                continue
            d["_path"] = path
            out.append(d)
        except Exception as e:  # noqa
            print(f"  (skip {path}: {type(e).__name__})")
    return out


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Confronto bracket Substrate-RLVR (cancello §8).")
    ap.add_argument("--root", default="/content/drive/MyDrive/substrate_rlvr")
    ap.add_argument("--difficulty", type=int, default=None, help="confronta solo i run di questa difficolta'")
    ap.add_argument("--data", choices=["synthetic", "real"], default=None, help="confronta solo i run di questo dataset")
    args = ap.parse_args()
    reports = load_reports(args.root, difficulty=args.difficulty, data=args.data)
    print(f"caricati {len(reports)} eval_report.json da {args.root}")
    for r in reports:
        print(f"  - {r.get('bracket')} seed{r.get('seed')}: solve={r.get('solve_rate_genuino')} "
              f"false_proven={r.get('false_proven_count')} abstain_recall={r.get('abstain_recall')}  [{r['_path']}]")
    s = summarize(reports)
    print("\n=== CANCELLO §8 ===")
    print(json.dumps(s, ensure_ascii=False, indent=2))
    if s["thesis_supported"] is True:
        print("\n-> TESI SUPPORTATA: il witness-conditioning batte l'ablazione di >=5pp, zero falsi-proven.")
    elif s["thesis_supported"] is False:
        print("\n-> TESI FALSIFICATA (per questo dominio): effetto-witness < 5pp o falsi-proven>0. Morte pulita.")
    else:
        print("\n-> INCOMPLETO: mancano bracket B_plain_dpo e/o B_witness_dpo. Gira entrambi su >=3 seed.")
