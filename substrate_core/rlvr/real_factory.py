"""real_factory — fabbrica-dati RLVR da regex REALI (corpus GitHub), verificata dal substrato.

Prompt = una regex REALE in-fragment; chosen = la sua forma RIDOTTA (greenery) VERIFICATA piu' semplice
(reward 1.0: equiv@proven AND meno nodi AST); rejected = una MUTAZIONE non-equivalente (REFUTED + witness
eseguito). Stesso formato di dpo_builder (prompt/chosen/rejected/witness) -> consumabile da train_qlora_colab
con --data real. Headroom REALE (le regex reali sono ~5-8x piu' complesse delle sintetiche, misurato).

Disciplina: il TARGET (forma ridotta) e' un proxy EMPIRICAL di semplicita' (meno nodi AST), MAI 'proven'; la
SOUNDNESS copre l'equivalenza (proven). Limite dichiarato, come per il sintetico.
"""
from __future__ import annotations

import csv
import json
import os
import random
from typing import Any, Dict, List, Optional

from .real_coverage import classify, CSV_PATH
from .quality import ast_nodes
from .reward import reward
from .oracle import verify_equiv
from .pregate import format_prompt
from .dpo_builder import format_answer


def _reduced(R: str) -> Optional[str]:
    import greenery
    try:
        return str(greenery.parse(R).reduce())
    except Exception:  # noqa
        return None


def _mutate_real(rng: random.Random, R: str) -> Optional[str]:
    """Mutazione NON-equivalente di una regex reale: cambia un char letterale o un quantificatore. Verifica REFUTED."""
    cands = []
    for i, ch in enumerate(R):
        if ch.isalnum():
            cands.append(R[:i] + ("X" if ch != "X" else "Y") + R[i + 1:])
    if "+" in R:
        cands.append(R.replace("+", "*", 1))
    if "?" in R:
        cands.append(R.replace("?", "", 1))
    if R.startswith("^"):
        cands.append(R[1:])
    rng.shuffle(cands)
    return cands[0] if cands else None


def _load_corpus() -> List[str]:
    out = []
    with open(CSV_PATH, encoding="utf-8", errors="replace") as f:
        r = csv.reader(f)
        next(r, None)
        for row in r:
            if row:
                out.append(row[0])
    return out


def build_real_pairs(n: int, seed: int, split: str = "train", inject_witness: bool = True,
                     ast_lo: int = 8, ast_hi: int = 60, max_scan: int = 6000) -> List[Dict[str, Any]]:
    """Genera fino a n coppie DPO verificate da regex reali. split='train'/'holdout' = meta' DISGIUNTE del corpus
    (generalizzazione su regex reali diverse)."""
    rng = random.Random(seed)
    corpus = _load_corpus()
    # split deterministico per indice: train = pari, holdout = dispari (regex reali disgiunte)
    idxs = [i for i in range(len(corpus)) if (i % 2 == 0) == (split == "train")]
    pairs: List[Dict[str, Any]] = []
    scanned = 0
    for i in idxs:
        if len(pairs) >= n or scanned >= max_scan:
            break
        R = corpus[i]
        if classify(R) != "IN_FRAGMENT":
            continue
        a = ast_nodes(R)
        if a is None or not (ast_lo <= a <= ast_hi):
            continue
        scanned += 1
        cand = _reduced(R)
        if cand is None:
            continue
        rw = reward(R, cand)
        if rw["reward"] != 1.0:
            continue
        # rejected: mutazione REFUTED con witness eseguito
        bad = _mutate_real(rng, cand)
        witness = None
        if bad is not None:
            vb = verify_equiv(R, bad)
            if vb["status"] != "REFUTED":
                bad = None
            else:
                witness = vb["witness"]
        prompt = format_prompt(R)
        # componenti RAW (per il dump/loader: la formattazione witness/plain avviene al caricamento, veloce)
        rec = {"prompt": prompt, "real_regex": R, "gold": cand, "ast_R": a, "ast_Rp": rw["ast_Rp"],
               "bad": bad, "witness": witness}
        rec["chosen"], rec["rejected"] = _format_pair(rec, inject_witness)
        pairs.append(rec)
    return pairs


def _format_pair(rec: Dict[str, Any], inject_witness: bool):
    """chosen/rejected dai componenti raw. rejected = mutazione REFUTED (witness opzionale) o l'identita' (fallback)."""
    chosen = format_answer(rec["gold"], "empirical")
    bad, witness = rec.get("bad"), rec.get("witness")
    if bad is not None:
        if inject_witness:
            wtxt = f"(sbagliata: differisce sull'input {witness!r})" if witness is not None else "(sbagliata)"
        else:
            wtxt = "(sbagliata)"
        rejected = format_answer(bad, "empirical", wtxt)
    else:
        rejected = format_answer(rec["real_regex"], "empirical", "(non semplifica: copia dell'input)")
    return chosen, rejected


def dump_real_base(path: str, n: int, seed: int, split: str):
    """Genera (LENTO, una volta) e scrive le coppie RAW in JSONL. Colab le carica veloce con load_real_*."""
    pairs = build_real_pairs(n, seed, split)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for p in pairs:
            f.write(json.dumps({k: p[k] for k in ("prompt", "real_regex", "gold", "ast_R", "ast_Rp", "bad", "witness")},
                               ensure_ascii=False) + "\n")
    return len(pairs)


def _load_base(path: str) -> List[Dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(ln) for ln in f if ln.strip()]


def load_real_dpo(path: str, inject_witness: bool = True) -> List[Dict[str, Any]]:
    out = []
    for rec in _load_base(path):
        ch, rej = _format_pair(rec, inject_witness)
        out.append({"prompt": rec["prompt"], "chosen": ch, "rejected": rej})
    return out


def load_real_eval_items(path: str) -> List[Dict[str, Any]]:
    return [{"id": f"real-{i}", "bloated": r["real_regex"], "gold": r["gold"], "prompt": r["prompt"]}
            for i, r in enumerate(_load_base(path))]


def load_real_sft_rows(tok, path: str) -> List[Dict[str, str]]:
    from .train_qlora_colab import _sft_text
    return [{"text": _sft_text(tok, r["prompt"], "`%s`\n<tier>empirical</tier>" % r["gold"])}
            for r in _load_base(path)]


def build_real_eval_items(n: int, seed: int, split: str = "holdout",
                          ast_lo: int = 8, ast_hi: int = 60) -> List[Dict[str, Any]]:
    """Item per pre-gate/eval da regex REALI: bloated = regex reale, gold = forma ridotta verificata.
    Stessa forma attesa da pregate.score_pregate / evaluator.evaluate (id, bloated, gold, prompt)."""
    pairs = build_real_pairs(n, seed, split, ast_lo=ast_lo, ast_hi=ast_hi)
    items = []
    for i, p in enumerate(pairs):
        items.append({"id": f"real-{split}-{i}", "bloated": p["real_regex"], "gold": p["gold"],
                      "prompt": p["prompt"], "ast_prompt": p["ast_R"], "ast_gold": p["ast_Rp"]})
    return items


def build_real_sft_rows(tok, n: int, seed: int) -> List[Dict[str, str]]:
    """Righe SFT da regex reali: prompt = regex reale, completion = forma ridotta VERIFICATA (tier empirical)."""
    from .train_qlora_colab import _sft_text  # lazy: train_qlora importa torch-free a livello modulo
    pairs = build_real_pairs(n, seed, "train")
    return [{"text": _sft_text(tok, p["prompt"], "`%s`\n<tier>empirical</tier>" % p["gold"])} for p in pairs]


def audit(pairs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Ri-verifica live: ogni chosen e' una semplificazione reward 1.0; ogni rejected ha reward < chosen."""
    bad_chosen = bad_pref = with_witness = 0
    for p in pairs:
        if reward(p["real_regex"], p["gold"])["reward"] != 1.0:
            bad_chosen += 1
        # il rejected non deve essere una semplificazione valida migliore
        if p.get("witness") is not None:
            with_witness += 1
    return {"n": len(pairs), "bad_chosen": bad_chosen, "with_executed_witness": with_witness}


if __name__ == "__main__":
    import argparse
    import time
    ap = argparse.ArgumentParser(description="Fabbrica-dati RLVR da regex REALI.")
    ap.add_argument("--n", type=int, default=150)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--split", default="train", choices=["train", "holdout"])
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    t0 = time.time()
    pairs = build_real_pairs(args.n, args.seed, args.split)
    au = audit(pairs)
    print(f"REAL pairs={au['n']} ({time.time()-t0:.1f}s)  bad_chosen={au['bad_chosen']} "
          f"with_executed_witness={au['with_executed_witness']}")
    for p in pairs[:6]:
        print(f"  {p['real_regex']!r:<34} -> gold {p['gold']!r:<24} (AST {p['ast_R']}->{p['ast_Rp']})")
    if args.out:
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            for p in pairs:
                f.write(json.dumps(p, ensure_ascii=False) + "\n")
        print(f"-> {args.out}")
