"""substrate_core.rlvr.factory — la FABBRICA-DATI a 3 canali (oracolo-come-motore-dati, batte crepa #3).

L'oracolo regex_equiv e' COMPLETO+SOUND -> possiamo GENERARE PER COSTRUZIONE tuple a label perfetta,
senza modello nel loop (scavalca il ceiling da rejection-sampling). Tre canali:

  Canale A (PROVEN-piu'-semplice): da una regex SEMPLICE seed, un BLOAT-generator produce una forma
    equivalente piu' complessa (R_bloated). Il task = "semplifica R_bloated"; la risposta gold = R_simple.
    SELF-CHECK: emessa solo se reward(R_bloated, R_simple)==1.0 (equivalente@proven E AST piu' basso).
  Canale B (REFUTED+witness): muta R_simple in R_bad NON-equivalente -> status REFUTED + stringa
    distinguente ESEGUITA. Diventa il 'rejected' (sound e gratis) per il builder DPO.
  Canale C (ABSTAIN-injection, OBBLIGATORIO): casi unicode-shorthand (\\w \\W \\s \\S) e non-regolari
    (backref/lookaround) che il generatore NON produce mai -> danno VARIANZA al tier-head al confine
    ABSTAIN (sul frammento regolare il tier ha entropia ZERO). Senza canale C il tier-head non si addestra.

TRAIN vs HOLDOUT a REGOLE DISGIUNTE (anti-overfit, crepa #5): i bloat-operator di train e holdout sono
insiemi DISGIUNTI, cosi' "batte il base" misura generalizzazione, non memorizzazione della tabella.
Tutto greenery-parsabile (no '(?:...)'/'\\d' nel frammento generato: ast_nodes userebbe None).
"""
from __future__ import annotations

import json
import random
from typing import Any, Callable, Dict, List, Optional

from .oracle import verify_equiv
from .quality import ast_nodes
from .reward import reward

ALPHABET = ["a", "b", "c"]

# DIFFICOLTA' -> (max_depth, p_stop, n_bloat). Il lever principale e' la COMPLESSITA' della seed (depth + p_stop
# basso = regex piu' profonde/lunghe): su regex complesse il modello sbaglia piu' spesso l'EQUIVALENZA (-> REFUTED
# -> reward 0), creando headroom E dando al witness piu' da insegnare. n_bloat = quanti strati di bloat comporre.
_DIFF = {1: (2, 0.40, 1), 2: (3, 0.28, 1), 3: (4, 0.18, 2)}


def _rand_simple(rng: random.Random, depth: int = 0, max_depth: int = 2, p_stop: float = 0.4) -> str:
    """Una regex regolare 'semplice' casuale: char / classe / concat / alt / quantificata. Bounded.
    max_depth e p_stop controllano la COMPLESSITA' (piu' profondo / p_stop piu' basso = regex piu' grandi)."""
    if depth >= max_depth or rng.random() < p_stop:
        atom = rng.choice(ALPHABET)
        if rng.random() < 0.25:
            a, b = sorted(rng.sample(ALPHABET, 2))
            atom = f"[{a}{b}]"
        q = rng.choice(["", "", "", "+", "*", "?", "{1,3}", "{2}"])
        return atom + q
    op = rng.choice(["concat", "concat", "alt", "group"])   # concat pesato: regex piu' lunghe a parita' di depth
    if op == "concat":
        return _rand_simple(rng, depth + 1, max_depth, p_stop) + _rand_simple(rng, depth + 1, max_depth, p_stop)
    if op == "alt":
        return "(" + _rand_simple(rng, depth + 1, max_depth, p_stop) + "|" + \
               _rand_simple(rng, depth + 1, max_depth, p_stop) + ")"
    return "(" + _rand_simple(rng, depth + 1, max_depth, p_stop) + ")" + rng.choice(["", "+", "*"])


# ---------------------------------------------------------------------------
# BLOAT-operator: R_simple -> R_bloated equivalente ma piu' complesso. TRAIN/HOLDOUT disgiunti.
# (La correttezza non dipende dall'astuzia: il self-check reward()==1.0 scarta ogni op che fallisce.)
# ---------------------------------------------------------------------------
BLOAT_OPS: Dict[str, Callable[[str], str]] = {
    # --- gruppo TRAIN ---
    "paren2":   lambda s: f"(({s}))",
    "dupalt":   lambda s: f"({s}|{s})",
    "unitquant": lambda s: f"({s}){{1}}",
    # --- gruppo HOLDOUT (disgiunto) ---
    "paren3":   lambda s: f"((({s})))",
    "tripalt":  lambda s: f"({s}|{s}|{s})",
    "altquant": lambda s: f"({s}|{s}){{1}}",
}
TRAIN_RULES = ["paren2", "dupalt", "unitquant"]
HOLDOUT_RULES = ["paren3", "tripalt", "altquant"]


# ---------------------------------------------------------------------------
# OBFUSCATION ALGEBRICA (difficolta' >=2): la SOLA via a meno nodi e' RAGIONARE (factoring / riconoscere un
# quantificatore), NON copiare un sotto-termine. `simple` NON e' substring di `bloated` -> niente shortcut di copia.
# TRAIN/HOLDOUT usano op DISGIUNTE (anti-overfit, crepa #5): factoring-prefisso+plus vs factoring-suffisso+count.
# ---------------------------------------------------------------------------
def _rand_atom(rng: random.Random, allow_quant: bool = True, allow_class: bool = True) -> str:
    a = rng.choice(ALPHABET)
    if allow_class and rng.random() < 0.3:
        x, y = sorted(rng.sample(ALPHABET, 2))
        a = f"[{x}{y}]"
    if allow_quant and rng.random() < 0.4:
        a = a + rng.choice(["+", "*", "?"])
    return a


def _algebraic_obfuscation(rng: random.Random, op: str, complexity: int):
    """Ritorna (simple, bloated): bloated equivalente ma con PIU' nodi, riducibile SOLO RICONOSCENDO una
    ripetizione (NON copiando un sotto-termine: `simple` non e' substring di `bloated`). NB verificato eseguendo:
    il factoring (ab|ac->a(b|c)) AUMENTA i nodi -> NON e' una semplificazione qui; la leva e' il riconoscimento."""
    big = complexity >= 2
    A = _rand_atom(rng, allow_quant=False, allow_class=not big)
    if op == "plus":                                       # GG* -> G+   (riconoscere il '+')
        inner = (A + _rand_atom(rng, allow_quant=False, allow_class=False)) if big else A
        G = f"({inner})"
        return f"{G}+", f"{G}{G}*"
    if op == "count":                                      # AA..A (n volte) -> A{n}
        n = rng.randint(2, 4 if big else 3)
        return f"{A}{{{n}}}", A * n
    if op == "countadd":                                   # A{m}A{n} -> A{m+n}
        m, n = rng.randint(1, 2), rng.randint(2, 3)
        return f"{A}{{{m + n}}}", f"{A}{{{m}}}{A}{{{n}}}"
    # countrange: (A|AA|AAA) -> A{1,k}
    k = rng.randint(2, 3)
    expanded = "|".join(A * i for i in range(1, k + 1))
    return f"{A}{{1,{k}}}", f"({expanded})"


# Tutte e 4 le skill di riconoscimento per ENTRAMBI gli split: la generalizzazione e' su ISTANZE diverse
# (seed train != seed holdout), il test ML standard. (La disgiunzione-di-regole resta solo per difficolta' 1.)
_ALL_OBF = ["plus", "count", "countadd", "countrange"]
TRAIN_OBF = _ALL_OBF
HOLDOUT_OBF = _ALL_OBF


def _mutate_nonequiv(rng: random.Random, s: str) -> Optional[str]:
    """Muta s in una forma NON-equivalente (per il canale B). Ritorna None se non ci riesce."""
    cands = []
    # cambia un char dell'alfabeto in un altro
    for i, ch in enumerate(s):
        if ch in ALPHABET:
            other = rng.choice([c for c in ALPHABET if c != ch])
            cands.append(s[:i] + other + s[i + 1:])
    # cambia un quantificatore (+ <-> *: a+ vs a* NON equivalenti, '' li distingue)
    cands += [s.replace("+", "*", 1)] if "+" in s else []
    cands += [s.replace("?", "", 1)] if "?" in s else []
    cands += [s + rng.choice(ALPHABET)]  # appendi un char (cambia il linguaggio)
    rng.shuffle(cands)
    return cands[0] if cands else None


# ---------------------------------------------------------------------------
# Canale C — catalogo ABSTAIN/REFUTED iniettato a mano (OBBLIGATORIO)
# ---------------------------------------------------------------------------
def abstain_catalog() -> List[Dict[str, Any]]:
    """Casi-confine che il generatore non produce mai: danno varianza al tier-head."""
    cases = [
        ("a\\w+", "a\\w+", "abstain", "unicode-shorthand \\w (semantica unicode non modellata)"),
        ("\\W", "\\W", "abstain", "unicode-shorthand \\W"),
        ("a\\s", "a\\s", "abstain", "unicode-shorthand \\s"),
        ("\\S+", "\\S+", "abstain", "unicode-shorthand \\S"),
        ("(a)\\1", "(a)\\1", "abstain", "backref \\1 (non-regolare)"),
        ("a(?=b)", "a(?=b)", "abstain", "lookahead (non-regolare)"),
    ]
    out = []
    for r1, r2, expected, note in cases:
        v = verify_equiv(r1, r2)
        out.append({"channel": "C", "prompt_regex": r1, "completion": r2,
                    "label": "abstain", "expected_status": "ABSTAIN", "got_status": v["status"],
                    "witness": v["witness"], "content_hash": v["content_hash"], "note": note})
    return out


# ---------------------------------------------------------------------------
# Generazione dei TASK (un task = prompt bloated + gold-simple + distrattore-refuted)
# ---------------------------------------------------------------------------
def generate_tasks(n: int, seed: int, rule_groups: List[str], difficulty: int = 1,
                   obf_ops: Optional[List[str]] = None, max_tries: int = 200) -> List[Dict[str, Any]]:
    """difficulty 1 = bloat MECCANICO (togli-il-guscio, facile). difficulty >=2 = obfuscation ALGEBRICA
    (factoring/riconoscimento, niente shortcut di copia): l'unica via a meno nodi e' ragionare -> headroom reale."""
    rng = random.Random(seed)
    max_depth, p_stop, n_bloat = _DIFF.get(difficulty, _DIFF[1])
    obf_ops = obf_ops or TRAIN_OBF
    tasks: List[Dict[str, Any]] = []
    tries = 0
    seen_prompts = set()
    while len(tasks) < n and tries < n * max_tries:
        tries += 1
        if difficulty <= 1:
            simple = _rand_simple(rng, max_depth=max_depth, p_stop=p_stop)
            op_names = [rng.choice(rule_groups) for _ in range(n_bloat)]
            bloated = simple
            for op_name in op_names:                   # compone n_bloat strati di bloat MECCANICO
                bloated = BLOAT_OPS[op_name](bloated)
        else:
            op_names = [rng.choice(obf_ops)]
            simple, bloated = _algebraic_obfuscation(rng, op_names[0], complexity=difficulty - 1)
        if bloated in seen_prompts:
            continue
        # SELF-CHECK canale A: bloated -> simple deve dare reward 1.0 (equiv@proven E piu' semplice)
        ra = reward(bloated, simple)
        if ra["reward"] != 1.0:
            continue
        # canale B: distrattore non-equivalente con witness eseguito
        bad = _mutate_nonequiv(rng, simple)
        refuted = None
        if bad is not None:
            vb = verify_equiv(bloated, bad)
            if vb["status"] == "REFUTED":
                refuted = {"completion": bad, "witness": vb["witness"],
                           "content_hash": vb["content_hash"]}
        seen_prompts.add(bloated)
        tasks.append({
            "task_id": f"{seed}-{len(tasks)}",
            "rule": op_names[0], "rules": op_names, "difficulty": difficulty,
            "prompt_regex": bloated,
            "proven_completion": simple,
            "ast_prompt": ra["ast_R"], "ast_completion": ra["ast_Rp"],
            "content_hash": ra["content_hash"],
            "refuted": refuted,   # None se non si e' trovato un distrattore REFUTED
        })
    return tasks


def to_records(tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Espande i task in record JSONL per-canale (A: proven; B: refuted; piu' il catalogo C a parte)."""
    recs: List[Dict[str, Any]] = []
    for t in tasks:
        recs.append({"channel": "A", "task_id": t["task_id"], "prompt_regex": t["prompt_regex"],
                     "completion": t["proven_completion"], "label": "proven",
                     "ast_prompt": t["ast_prompt"], "ast_completion": t["ast_completion"],
                     "content_hash": t["content_hash"], "rule": t["rule"]})
        if t["refuted"]:
            recs.append({"channel": "B", "task_id": t["task_id"], "prompt_regex": t["prompt_regex"],
                         "completion": t["refuted"]["completion"], "label": "refuted",
                         "witness": t["refuted"]["witness"],
                         "content_hash": t["refuted"]["content_hash"], "rule": t["rule"]})
    return recs


def build_split(n: int, seed: int, split: str, difficulty: int = 1) -> List[Dict[str, Any]]:
    """split='train' o 'holdout' (op DISGIUNTE per testare la generalizzazione, non la memorizzazione).
    difficulty 1 = bloat meccanico (facile); >=2 = obfuscation algebrica (headroom reale). C sempre incluso."""
    is_train = (split == "train")
    rules = TRAIN_RULES if is_train else HOLDOUT_RULES
    obf = TRAIN_OBF if is_train else HOLDOUT_OBF
    tasks = generate_tasks(n, seed, rules, difficulty=difficulty, obf_ops=obf)
    recs = to_records(tasks)
    recs += abstain_catalog()      # canale C in entrambi gli split
    return recs


def _write_jsonl(path: str, recs: List[Dict[str, Any]]) -> None:
    import os
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    import argparse
    import os
    ap = argparse.ArgumentParser(description="Fabbrica-dati Substrate-RLVR (regex_equiv).")
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "data"))
    ap.add_argument("--difficulty", type=int, default=1, choices=[1, 2, 3])
    args = ap.parse_args()
    train = build_split(args.n, args.seed, "train", difficulty=args.difficulty)
    holdout = build_split(max(20, args.n // 4), args.seed + 10_000, "holdout", difficulty=args.difficulty)
    _write_jsonl(os.path.join(args.out, "train.jsonl"), train)
    _write_jsonl(os.path.join(args.out, "holdout.jsonl"), holdout)
    print(f"train={len(train)} record (A+B+C), holdout={len(holdout)} record, difficulty={args.difficulty} -> {args.out}")
