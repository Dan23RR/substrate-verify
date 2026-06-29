"""substrate_core.semantic_hash — HASH SEMANTICO sul frammento regolare: l'indirizzo dipende dal COMPORTAMENTO.

Sul frammento REGOLARE il DFA MINIMO e' forma canonica unica (Myhill-Nerode), quindi
    H(r) = SHA-256(serializzazione canonica del DFA minimo di L(r))
gode di  H(r1)==H(r2) <=> L(r1)==L(r2)  RELATIVAMENTE al TCB di traduzione (greenery + ASCII).

RUOLO NEL LEDGER (disciplina): l'hash e' un BUCKETER CANDIDATO cheap, NON la prova. La soundness del collasso
viene dal GIUDICE (`regex_equiv`, che ri-esegue il controesempio sotto re.fullmatch NATIVO -> indipendente da
greenery). Quindi un hash imperfetto tocca solo la RECALL (equivalenze mancate = under-collapse, onesto), MAI la
soundness (un over-collapse e' catturato dal giudice e DEMOTATO ad ABSTAIN, mai coniato PROVEN).

TETTO DICHIARATO: (1) TCB = greenery + interpretazione ASCII; \\w/\\W/\\s/\\S -> None (fuori, come ABSTAIN del gate).
(2) la divergenza greenery/Python-re sul '.'/'\\n' esiste a monte -> per questo il collasso NON e' fidato da solo:
e' il giudice (re.fullmatch) a decidere. Forma canonica RAPPRESENTAZIONE-INDIPENDENTE (assorbe i char irrilevanti).
"""
from __future__ import annotations

import hashlib
import re as _re
from typing import Optional

from .domains.regex_equiv import _to_greenery   # STESSA traduzione del giudice (TCB condiviso, dichiarato)

_OTHER = "￿"   # rappresentante di 'qualunque char non distinguente'
_SHORTHAND = _re.compile(r"\\[wWsS]")           # semantica unicode -> fuori dal frammento ASCII -> None


def canonical_from_fsm(fsm) -> str:
    """Forma canonica del LINGUAGGIO, indipendente dalla rappresentazione: raggruppa i char per funzione di
    transizione (Myhill-Nerode sull'alfabeto), ASSORBE in OTHER i char che si comportano come OTHER, ordina i
    blocchi canonicamente, BFS per id di stato canonici."""
    fsm = fsm.reduce()
    syms = list(fsm.alphabet)
    sigma = set()
    for s in syms:
        if not getattr(s, "negated", False):
            sigma |= set(s.get_chars())
    states = list(fsm.states)
    sidx = {st: i for i, st in enumerate(states)}

    def target(state, ch):
        row = fsm.map.get(state, {})
        for sym in syms:
            try:
                if sym.accepts(ch):
                    return row.get(sym)
            except Exception:  # noqa
                pass
        return None

    def sig(ch):
        return tuple(sidx.get(target(st, ch), -1) for st in states)

    allchars = sorted(sigma) + [_OTHER]
    other_sig = sig(_OTHER)
    groups = {}
    for ch in allchars:
        sg = sig(ch)
        if ch != _OTHER and sg == other_sig:
            continue                  # assorbito in OTHER -> niente enumerazione (canonicita')
        groups.setdefault(sg, set()).add(ch)

    def block_key(chs):
        return "~" if _OTHER in chs else "".join(sorted(chs))

    blocks = sorted(groups.values(), key=block_key)

    def block_target(state, chs):
        return target(state, _OTHER if _OTHER in chs else min(chs))

    order = {fsm.initial: 0}
    queue = [fsm.initial]
    while queue:
        st = queue.pop(0)
        for chs in blocks:
            t = block_target(st, chs)
            if t is not None and t not in order:
                order[t] = len(order)
                queue.append(t)
    finals = sorted(order[s] for s in fsm.finals if s in order)
    trans = []
    for st, cid in order.items():
        for chs in blocks:
            t = block_target(st, chs)
            if t in order:
                trans.append((cid, block_key(chs), order[t]))
    trans.sort()
    return "DFAv3|n=%d|init=0|fin=%s|trans=%s" % (len(order), finals, trans)


def semantic_hash(pattern: str) -> Optional[str]:
    """Hash comportamentale di una regex (frammento regolare). None se fuori frammento (unicode-shorthand) o non
    parsabile -> il chiamante NON la bucketizza (coerente con l'ABSTAIN del gate)."""
    if not isinstance(pattern, str) or _SHORTHAND.search(pattern):
        return None
    try:
        import greenery
        canon = canonical_from_fsm(greenery.parse(_to_greenery(pattern)).to_fsm())
        return hashlib.sha256(canon.encode("utf-8")).hexdigest()
    except Exception:  # noqa  (backref/lookaround/sintassi non gestita -> fuori frammento)
        return None


__all__ = ["semantic_hash", "canonical_from_fsm"]
