"""substrate_core.rlvr.evaluator — VALUTATORE-CON-TIER + calibrazione (il cancello §8, misurato onesto).

Metriche, ogni numero prodotto da questo script:
  PRIMARIA  SOLVE-RATE-GENUINO = frazione di output con reward(bloated,R')==1.0
            (CONFIRMED@proven AND piu' semplice AND non-identita'). NON la sola %CONFIRMED (hackerabile).
  VINCOLO DURO  FALSI-PROVEN == 0 (peccato cardinale): il modello dichiara tier 'proven' ma il substrato
            da REFUTED/ABSTAIN. Qualunque valore>0 INVALIDA il checkpoint a prescindere dall'accuracy.
  ECE       Expected Calibration Error sul tier-head, calcolato SOLO al confine ABSTAIN (canale C iniettato):
            sul frammento regolare il tier ha entropia ZERO (tutti 'proven') -> ECE globale sarebbe vuoto.
  RISK-COVERAGE  curva selective-accuracy/coverage + AURC.

Il tier dichiarato e' parsato dal testo (<tier>...</tier>); non-parsabile -> 'abstain' conservativo
(non puo' creare un falso-proven). Caso-limite: witness REFUTED puo' essere la STRINGA VUOTA '' (reale).
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from .oracle import verify_equiv
from .reward import reward
from .pregate import extract_regex

_TIER = re.compile(r"<tier>\s*(proven|empirical|abstain)\s*</tier>", re.I)
_CONF = re.compile(r"<conf>\s*([01](?:\.\d+)?)\s*</conf>", re.I)


def parse_tier(output: str) -> str:
    """Tier dichiarato dal modello. Non-parsabile -> 'abstain' (conservativo: mai un falso-proven spurio)."""
    if not output:
        return "abstain"
    m = _TIER.search(output)
    return m.group(1).lower() if m else "abstain"


def parse_conf(output: str) -> Optional[float]:
    """Confidenza ESPLICITA del modello in [0,1] da <conf>...</conf>. None se non emessa: l'ECE continua
    NON e' misurabile onestamente senza una confidenza emessa dal modello (un tier non e' una confidenza)."""
    if not output:
        return None
    m = _CONF.search(output)
    return float(m.group(1)) if m else None


def _is_false_proven(bloated: str, output: str) -> bool:
    """Falso-proven = dichiara 'proven' ma il substrato NON conferma l'equivalenza@proven."""
    if parse_tier(output) != "proven":
        return False
    rp = extract_regex(output)
    if rp is None:
        return True   # dichiara proven ma non produce una regex verificabile -> falso-proven
    v = verify_equiv(bloated, rp)
    return not (v["status"] == "CONFIRMED" and v["assurance"] == "proven")


def expected_calibration_error(conf_correct: List[Tuple[float, bool]], n_bins: int = 10) -> float:
    """ECE = sum_b (n_b/N) * |acc_b - conf_b|. Input: lista di (confidenza_dichiarata, tier_corretto?)."""
    if not conf_correct:
        return 0.0
    N = len(conf_correct)
    ece = 0.0
    for b in range(n_bins):
        lo, hi = b / n_bins, (b + 1) / n_bins
        bucket = [(c, ok) for (c, ok) in conf_correct if (lo < c <= hi) or (b == 0 and c == 0.0)]
        if not bucket:
            continue
        conf = sum(c for c, _ in bucket) / len(bucket)
        acc = sum(1 for _, ok in bucket if ok) / len(bucket)
        ece += (len(bucket) / N) * abs(acc - conf)
    return ece


def risk_coverage(scored: List[Tuple[float, bool]]) -> Dict[str, Any]:
    """Curva selective-accuracy/coverage: ordina per confidenza DESC, per ogni prefisso (coverage)
    riporta la selective-accuracy. AURC = media delle accuracy ai vari coverage (piu' basso = meglio il rischio)."""
    if not scored:
        return {"curve": [], "aurc": None}
    s = sorted(scored, key=lambda x: x[0], reverse=True)
    curve, correct = [], 0
    risks = []
    for i, (_, ok) in enumerate(s, start=1):
        correct += int(ok)
        cov = i / len(s)
        acc = correct / i
        curve.append({"coverage": round(cov, 4), "selective_accuracy": round(acc, 4)})
        risks.append(1.0 - acc)
    return {"curve": curve, "aurc": round(sum(risks) / len(risks), 4)}


def evaluate(items: List[Dict[str, Any]], outputs_by_id: Dict[str, str]) -> Dict[str, Any]:
    """items: holdout (ognuno con 'id','bloated'[, 'gold'] e opz. 'expected_status' per i casi ABSTAIN).
    outputs_by_id: id -> output di TESTO del modello (regex + <tier> + opz. <conf>). Ritorna il dict di metriche.

    CALIBRAZIONE ONESTA: un tier NON e' una confidenza. L'ECE continua e' calcolata SOLO sui casi in cui il
    modello emette una <conf> esplicita (None altrimenti, non un numero fuorviante). Sempre calcolabili invece:
    tier_reliability (accuratezza per tier dichiarato) e abstain_recall (sui casi-confine iniettati)."""
    n = solved = false_proven = nonparse = 0
    tier_tot = {"proven": 0, "empirical": 0, "abstain": 0}
    tier_ok_cnt = {"proven": 0, "empirical": 0, "abstain": 0}
    abstain_cases = abstain_hit = 0
    conf_correct: List[Tuple[float, bool]] = []   # solo dove <conf> e' emessa
    rc_points: List[Tuple[float, bool]] = []
    for it in items:
        out = outputs_by_id.get(it["id"])
        if out is None:
            continue
        n += 1
        tier = parse_tier(out)
        conf = parse_conf(out)
        rp = extract_regex(out)
        if rp is None:
            nonparse += 1
        is_abstain_case = it.get("expected_status") == "ABSTAIN"
        if not is_abstain_case and rp is not None and reward(it["bloated"], rp)["reward"] == 1.0:
            solved += 1
        if _is_false_proven(it["bloated"], out):
            false_proven += 1
        # correttezza del tier dichiarato
        if is_abstain_case:
            abstain_cases += 1
            tier_ok = (tier == "abstain")
            if tier == "abstain":
                abstain_hit += 1
        else:
            v = verify_equiv(it["bloated"], rp) if rp is not None else {"status": "ABSTAIN", "assurance": "none"}
            equiv_ok = (v["status"] == "CONFIRMED" and v["assurance"] == "proven")
            tier_ok = (tier in ("proven", "empirical")) == equiv_ok
        tier_tot[tier] += 1
        tier_ok_cnt[tier] += int(tier_ok)
        if conf is not None:
            conf_correct.append((conf, bool(tier_ok)))
        # risk-coverage: ordina per confidenza emessa, altrimenti per ordinale-tier (proxy dichiarato)
        rc_conf = conf if conf is not None else {"proven": 1.0, "empirical": 0.6, "abstain": 0.0}[tier]
        rc_points.append((rc_conf, bool(tier_ok)))
    solve_items = [it for it in items if it.get("expected_status") != "ABSTAIN" and it["id"] in outputs_by_id]
    tier_reliability = {t: {"n": tier_tot[t], "accuracy": (tier_ok_cnt[t] / tier_tot[t]) if tier_tot[t] else None}
                        for t in tier_tot}
    return {
        "n": n,
        "solve_rate_genuino": (solved / len(solve_items)) if solve_items else 0.0,
        "n_solve_items": len(solve_items),
        "false_proven_count": false_proven,
        "false_proven_violation": false_proven > 0,    # VINCOLO DURO == 0
        "nonparse_rate": (nonparse / n) if n else 0.0,
        "tier_reliability": tier_reliability,
        "abstain_recall": (abstain_hit / abstain_cases) if abstain_cases else None,
        "n_abstain_cases": abstain_cases,
        "ece": (round(expected_calibration_error(conf_correct), 4) if conf_correct else None),
        "ece_measurable": bool(conf_correct),   # False se il modello non ha emesso <conf>
        "risk_coverage": risk_coverage(rc_points),
    }


__all__ = ["evaluate", "parse_tier", "parse_conf", "expected_calibration_error", "risk_coverage"]
