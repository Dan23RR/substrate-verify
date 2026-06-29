"""substrate_core.rlvr.dpo_builder — coppie DPO WITNESS-CONDITIONED (consuma il "perche'", crepa #4).

DPO vanilla consuma solo (chosen, rejected) e butta il witness del REFUTED. Qui INIETTIAMO la stringa
distinguente ESEGUITA nel testo del rejected, cosi' il "perche'" del fallimento entra nella loss DPO
standard SENZA modificare l'algoritmo. ONESTO: e' un PROXY testuale, NON una garanzia che il modello
internalizzi la causa invece della preferenza superficiale -> da MISURARE al cancello §8, non assumere.

Tre tipi di coppia:
  (i)  chosen = semplificazione proven  ;  rejected = R_bad REFUTED + witness iniettato (+ falso 'proven').
  (ii) chosen = semplificazione proven  ;  rejected = IDENTITA' (copia dell'input, reward 0) -> colpisce crepa #1.
  (iii) CALIBRAZIONE (canale C): chosen = ABSTAIN motivato ; rejected = falso 'proven' su caso unicode.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from .factory import generate_tasks, abstain_catalog, TRAIN_RULES
from .pregate import format_prompt
from .reward import reward


def format_answer(regex: str, tier: str, note: str = "") -> str:
    """Formato di risposta canonico: la regex in backtick + il tier dichiarato. Il tier-head e' parsato di qui."""
    s = f"`{regex}`\n<tier>{tier}</tier>"
    return s + (f" {note}" if note else "")


def build_dpo_pairs(n: int, seed: int, rule_groups: Optional[List[str]] = None,
                    inject_witness: bool = True, difficulty: int = 1) -> List[Dict[str, Any]]:
    """inject_witness=True -> la distinguishing_string ESEGUITA entra nel testo del rejected (bracket B_witness).
    inject_witness=False -> rejected SENZA witness (bracket B_plain): ABLAZIONE PULITA. La differenza B_witness
    vs B_plain (stessi dati/seed/budget/algoritmo) isola l'UNICO ingrediente con bit-extra reali (~2 bit/REFUTED)."""
    rule_groups = rule_groups or TRAIN_RULES
    tasks = generate_tasks(n, seed, rule_groups, difficulty=difficulty)
    pairs: List[Dict[str, Any]] = []
    # TIER COERENTE: i pair-task usano 'empirical' SIA su chosen SIA su rejected (il segnale DPO e' la REGEX, non
    # il tag). 'abstain' compare SOLO nelle 6 coppie di calibrazione. Cosi' il DPO NON impara "proven->male" (che
    # faceva collassare il modello su abstain ovunque, verificato in run reale: B_witness solve 0.24, abstain 86/86).
    for t in tasks:
        prompt = format_prompt(t["prompt_regex"])
        chosen = format_answer(t["proven_completion"], "empirical")
        # (i) rejected = distrattore REFUTED; witness iniettato SOLO se richiesto (ablazione)
        if t["refuted"]:
            w = t["refuted"]["witness"]
            if inject_witness:
                rtxt = (f"(sbagliata: differisce sull'input {w!r})" if w is not None
                        else "(sbagliata: non equivalente)")
            else:
                rtxt = "(sbagliata)"   # NESSUN witness -> ablazione: solo la preferenza, non il 'perche'
            pairs.append({
                "type": "i_refuted_witness", "prompt": prompt, "chosen": chosen,
                "rejected": format_answer(t["refuted"]["completion"], "empirical", rtxt),
                "witness": (w if inject_witness else None), "task_id": t["task_id"],
            })
        # (ii) rejected = IDENTITA' (copia dell'input) -> reward 0, colpisce la saturazione crepa #1
        pairs.append({
            "type": "ii_identity", "prompt": prompt, "chosen": chosen,
            "rejected": format_answer(t["prompt_regex"], "empirical", "(non semplifica: copia dell'input)"),
            "task_id": t["task_id"],
        })
    # (iii) coppie di CALIBRAZIONE al confine ABSTAIN (l'UNICO posto dove appare 'abstain')
    for c in abstain_catalog():
        p = format_prompt(c["prompt_regex"])
        pairs.append({
            "type": "iii_calibration_abstain", "prompt": p,
            "chosen": format_answer(c["completion"], "abstain", f"({c['note']})"),
            "rejected": format_answer(c["completion"], "empirical"),
            "task_id": "C-" + c["prompt_regex"],
        })
    return pairs


def audit_pairs(pairs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Controlli di sanita' sulle coppie (no GPU). Ritorna conteggi + flag di violazione."""
    n_witness = sum(1 for p in pairs if p["type"] == "i_refuted_witness" and p.get("witness") is not None
                    and (repr(p["witness"]) in p["rejected"]))
    n_calib = sum(1 for p in pairs if p["type"] == "iii_calibration_abstain" and "abstain" in p["chosen"])
    n_same = sum(1 for p in pairs if p["chosen"] == p["rejected"])
    return {"total": len(pairs), "with_injected_witness": n_witness,
            "calibration_abstain": n_calib, "chosen_equals_rejected": n_same}


if __name__ == "__main__":
    import argparse
    import os
    ap = argparse.ArgumentParser(description="Builder coppie DPO witness-conditioned.")
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "data", "dpo_pairs.jsonl"))
    ap.add_argument("--no-witness", action="store_true", help="ablazione: rejected SENZA witness (bracket B_plain)")
    ap.add_argument("--difficulty", type=int, default=1, choices=[1, 2, 3])
    args = ap.parse_args()
    pairs = build_dpo_pairs(args.n, args.seed, inject_witness=not args.no_witness, difficulty=args.difficulty)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        for p in pairs:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    print(f"DPO pairs={len(pairs)} -> {args.out}; audit={audit_pairs(pairs)}")
