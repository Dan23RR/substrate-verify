"""substrate_core.rlvr.pregate — ESPERIMENTO #0 (zero GPU): puo' FALSIFICARE il progetto a costo zero.

Tesi della crepa #3 (verificata in review): un verificatore FILTRA, non GENERA. RFT/STaR puo' rinforzare
solo i successi che il base GIA' produce a volte. Quindi PRIMA di addestrare qualunque cosa:

  Misura pass@k (k=8) del BASE Qwen-1.5B su un holdout di regex-simplify NON-identita'.
  SE pass@1 < 5%  ->  il loop non ha NULLA da amplificare  ->  progetto FALSIFICATO senza spendere una GPU.

Questo modulo NON gira il modello (no torch locale): costruisce l'holdout + il FORMATO-PROMPT esatto + il
PARSER-DI-ESTRAZIONE robusto + lo scorer pass@k. Sono gli stessi che useremo su Colab per misurare il base.
Lo scoring e' verificato in locale con output gold/spazzatura simulati.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from .factory import generate_tasks, TRAIN_RULES
from .reward import reward

# CREPA #3 ("niente da amplificare") = pass@K ~0, NON pass@1. pass@1 BASSO = MOLTO headroom (il base non risolve
# greedy -> il modello addestrato ha spazio per salire). CORREZIONE (2026-06-09): su regex REALI il base fa
# pass@1=0.0 ma pass@8=0.28 -> headroom IDEALE, NON morte. Inoltre la fabbrica usa il GOLD di greenery
# (ground-truth), non campiona dal base -> l'SFT impara comunque. Il kill resta solo come SANITY-FLOOR su pass@k.
DEATH_THRESHOLD_PASSK = 0.03
DEATH_THRESHOLD_PASS1 = DEATH_THRESHOLD_PASSK   # alias retro-compat (vecchi import)

PROMPT_TEMPLATE = (
    "Simplify the following regular expression to an EQUIVALENT one that is syntactically simpler "
    "(matches exactly the same strings). Do not change the language. Output ONLY the simplified regex "
    "on the last line, wrapped in single backticks.\n\nRegex: `{regex}`\nSimplified:"
)


def format_prompt(bloated_regex: str) -> str:
    return PROMPT_TEMPLATE.format(regex=bloated_regex)


# --- PARSER ROBUSTO: estrae la regex dall'output libero del modello ---
# I modelli Coder amano i fence ```lang (anche annidati: ```csharp\n`regex`\n```). Strategia:
# 1) togli i fence ```lang (3+ backtick + eventuale tag-linguaggio) lasciando il contenuto interno;
# 2) preferisci il contenuto in SINGOLI backtick (l'ultimo); 3) altrimenti l'ultima riga non-vuota ripulita.
# Un parser troppo severo SOTTOSTIMA pass@k e falsifica per artefatto -> robusto di proposito.
_FENCE3 = re.compile(r"`{3,}[A-Za-z0-9_+#-]*")
_BACKTICK = re.compile(r"`([^`\n]+)`")
_PREFIX = re.compile(r"^(simplified|answer|regex|result|csharp|python|re|output)\s*[:=]?\s*", re.I)


def extract_regex(model_output: str) -> Optional[str]:
    if not model_output:
        return None
    s = _FENCE3.sub("", model_output)          # rimuove ```lang / ``` (anche 4+ backtick), tiene il contenuto
    ticks = _BACKTICK.findall(s)
    if ticks:
        return ticks[-1].strip()
    for line in reversed(s.strip().splitlines()):
        line = _PREFIX.sub("", line.strip()).strip().strip("`").strip()
        if line:
            return line
    return None


def build_pregate_holdout(n: int, seed: int, difficulty: int = 1) -> List[Dict[str, Any]]:
    """Holdout di SOLE coppie regex-simplify NON-identita' (prompt = R_bloated, gold = R_simple noto).
    Usa il generatore TRAIN_RULES (qui non serve la disgiunzione: misuriamo il base, non addestriamo)."""
    tasks = generate_tasks(n, seed, TRAIN_RULES, difficulty=difficulty)
    items = []
    for t in tasks:
        items.append({
            "id": t["task_id"],
            "bloated": t["prompt_regex"],
            "gold": t["proven_completion"],
            "prompt": format_prompt(t["prompt_regex"]),
            "ast_prompt": t["ast_prompt"], "ast_gold": t["ast_completion"],
        })
    return items


def score_item(bloated: str, completions: List[str], k: int = 8) -> Dict[str, Any]:
    """Dato l'output del modello (lista di k campioni di TESTO), pass@k = >=1 campione la cui regex
    estratta vale reward(bloated, R')==1.0 (equivalente@proven E piu' semplice). Identita' esclusa dal reward."""
    sols = []
    for c in completions[:k]:
        rp = extract_regex(c)
        if rp is None:
            continue
        r = reward(bloated, rp)
        if r["reward"] == 1.0:
            sols.append(rp)
    return {"solved": len(sols) > 0, "n_solutions": len(sols), "first_solution": sols[0] if sols else None}


def score_pregate(items: List[Dict[str, Any]], outputs_by_id: Dict[str, List[str]],
                  k: int = 8) -> Dict[str, Any]:
    """pass@1 e pass@k sull'holdout. outputs_by_id[item_id] = lista di campioni di testo del base."""
    p1 = p_k = n = 0
    nonparse = 0
    for it in items:
        outs = outputs_by_id.get(it["id"], [])
        if not outs:
            continue
        n += 1
        s1 = score_item(it["bloated"], outs[:1], k=1)
        sk = score_item(it["bloated"], outs, k=k)
        p1 += int(s1["solved"])
        p_k += int(sk["solved"])
        if extract_regex(outs[0]) is None:
            nonparse += 1
    pass1 = p1 / n if n else 0.0
    passk = p_k / n if n else 0.0
    return {
        "n": n, "pass@1": pass1, "pass@k": passk, "k": k,
        "nonparse_rate": (nonparse / n if n else 0.0),
        "DEATH_THRESHOLD_pass@k": DEATH_THRESHOLD_PASSK,
        # KILL solo se pass@K ~0 (crepa #3: niente da rinforzare E sanity-floor). pass@1 basso = HEADROOM, non morte.
        "project_falsified_zero_gpu": (n > 0 and passk < DEATH_THRESHOLD_PASSK),
        "headroom": ("ALTO (base non risolve greedy -> spazio per salire)" if pass1 < 0.2 else "moderato"),
    }


def _write_jsonl(path: str, items: List[Dict[str, Any]]) -> None:
    import os
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    import argparse
    import os
    ap = argparse.ArgumentParser(description="Esperimento #0: holdout pre-gate per pass@k del base.")
    ap.add_argument("--n", type=int, default=80)
    ap.add_argument("--seed", type=int, default=777)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "data", "pregate_holdout.jsonl"))
    ap.add_argument("--difficulty", type=int, default=1, choices=[1, 2, 3])
    args = ap.parse_args()
    items = build_pregate_holdout(args.n, args.seed, difficulty=args.difficulty)
    _write_jsonl(args.out, items)
    print(f"pre-gate holdout: {len(items)} prompt non-identita' -> {args.out}")
    print(f"soglia di morte: pass@1 < {DEATH_THRESHOLD_PASS1} sul BASE => progetto falsificato a costo zero")
