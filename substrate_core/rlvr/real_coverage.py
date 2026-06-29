"""real_coverage — RISCONTRO REALE: che frazione delle regex del MONDO REALE (26.8k da GitHub, ordinate per
uso) cade nel frammento DECIDIBILE+SOUND del substrato (regex_equiv) vs ABSTAIN onesto?

Usa la logica del GATE REALE (_to_greenery + i guard di regex_equiv), in modo SICURO: solo PARSING (greenery),
mai re.fullmatch su regex reali (alcune sono ReDoS — il corpus viene dalla ricerca su ReDoS). Ogni numero qui
e' prodotto da questo script sul file reale data/real/github-regexp.csv.
"""
from __future__ import annotations

import csv
import os
import re
import statistics as st
from collections import Counter

from substrate_core.domains.regex_equiv import _to_greenery
from substrate_core.rlvr.quality import ast_nodes

CSV_PATH = os.path.join(os.path.dirname(__file__), "data", "real", "github-regexp.csv")

# i guard ESATTI del gate regex_equiv (domains/regex_equiv.py):
_SHORTHAND = re.compile(r"\\[wWsS]")                       # semantica unicode -> ABSTAIN (mai falso-proven)
_BACKREF = re.compile(r"\\[1-9]")                          # backreference -> non-regolare
_LOOKAROUND = re.compile(r"\(\?[=!<]")                     # lookahead/lookbehind -> non-regolare


def classify(pattern: str):
    """Replica la DECISIONE del gate (senza il cross-check costoso): in quale tier cade questa regex reale."""
    if _SHORTHAND.search(pattern):
        return "ABSTAIN_unicode_shorthand"
    if _BACKREF.search(pattern) or _LOOKAROUND.search(pattern):
        return "ABSTAIN_non_regular"
    try:
        import greenery
        greenery.parse(_to_greenery(pattern))             # solo PARSE (no to_fsm/no fullmatch -> sicuro+veloce)
        return "IN_FRAGMENT"
    except Exception:  # noqa
        return "ABSTAIN_unsupported_syntax"


def main(limit: int = 0):
    rows = []
    with open(CSV_PATH, encoding="utf-8", errors="replace") as f:
        r = csv.reader(f)
        next(r, None)                                     # header pattern,cnt
        for row in r:
            if not row:
                continue
            pat = row[0]
            try:
                cnt = int(row[1]) if len(row) > 1 and row[1].isdigit() else 1
            except Exception:  # noqa
                cnt = 1
            rows.append((pat, cnt))
    if limit:
        rows = rows[:limit]

    tally = Counter()
    weighted = Counter()                                  # pesato per frequenza d'uso (cnt): copertura REALE d'uso
    in_frag_ast = []
    in_frag_examples = []
    for pat, cnt in rows:
        c = classify(pat)
        tally[c] += 1
        weighted[c] += cnt
        if c == "IN_FRAGMENT":
            a = ast_nodes(pat)
            if a is not None:
                in_frag_ast.append(a)
            if len(in_frag_examples) < 12 and len(pat) > 4:
                in_frag_examples.append((pat, a))

    n = len(rows)
    wtot = sum(weighted.values())
    print(f"=== COPERTURA REALE del frammento sound (substrate regex_equiv) su {n} regex reali (GitHub) ===\n")
    print("  per-REGEX (conteggio unico):")
    for k in ("IN_FRAGMENT", "ABSTAIN_unicode_shorthand", "ABSTAIN_non_regular", "ABSTAIN_unsupported_syntax"):
        print(f"    {k:<28} {tally[k]:>6}  ({100*tally[k]/n:5.1f}%)")
    print("\n  per-USO (pesato per frequenza, copertura del mondo reale che gira davvero):")
    for k in ("IN_FRAGMENT", "ABSTAIN_unicode_shorthand", "ABSTAIN_non_regular", "ABSTAIN_unsupported_syntax"):
        print(f"    {k:<28} {weighted[k]:>8}  ({100*weighted[k]/wtot:5.1f}%)")

    if in_frag_ast:
        print(f"\n  complessita' AST delle regex IN-FRAGMENT (n={len(in_frag_ast)}): "
              f"media={st.mean(in_frag_ast):.1f} mediana={st.median(in_frag_ast)} "
              f"p90={sorted(in_frag_ast)[int(0.9*len(in_frag_ast))]} max={max(in_frag_ast)}")
        print("  (confronto: le mie regex SINTETICHE diff-2 avevano AST gap ~4; il modello le risolveva al 100%)")
        print("\n  esempi reali IN-FRAGMENT (pattern -> ast_nodes):")
        for pat, a in in_frag_examples:
            print(f"    {pat!r:<40} -> {a}")
    return tally, weighted, in_frag_ast


if __name__ == "__main__":
    import sys
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 0)
