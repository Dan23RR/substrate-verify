"""substrate_core.domains.regex_equiv — TIER FORMALE COMPLETO: equivalenza di regex DECISA per AUTOMI.

Perche' esiste (oltre smt): Z3-strings e' sound ma INCOMPLETO sull'equivalenza di regex (unknown su +/* di classi).
Ma l'equivalenza di LINGUAGGI REGOLARI e' DECIDIBILE: regex -> FSM -> uguaglianza di linguaggio (riduzione/min).
Oracolo FIDATO e COMPLETO (greenery, automi): mai 'unknown' sul frammento regolare.
  L(r1) == L(r2)  -> CONFIRMED / PROVEN (equivalenza su TUTTO lo spazio infinito; implica anche la .match-equivalenza)
  L(r1) != L(r2)  -> REFUTED + stringa MINIMA che le distingue, RI-VERIFICATA con re.fullmatch (controesempio sound)
  regex fuori dal frammento regolare (backref/lookaround) o non parsabile -> ABSTAIN(tipato)
Nessuna esecuzione di codice non-fidato: solo costruzione di automi -> niente host-escape/frame-walk. z3-free.
"""
from __future__ import annotations

import re as _re

from ..kernel import Claim, Verdict, Status, Domain, register, PROVEN


def _to_greenery(p: str) -> str:
    """Python-regex (sottoinsieme regolare) -> sintassi greenery: spoglia gruppi nominati/non-cattura, espande \\d \\w,
    normalizza \\. dentro le classi, toglie le ancore (greenery ragiona sul LINGUAGGIO = full-match)."""
    p = _re.sub(r"\(\?P<[^>]+>", "(", p)
    p = p.replace("(?:", "(")
    # dentro le classi [...]: \. -> .  e  \d -> 0-9 , \w -> 0-9A-Za-z_  (NIENTE bracket annidate -> niente NoMatch)
    p = _re.sub(r"\[([^\]]*)\]",
                lambda m: "[" + m.group(1).replace("\\.", ".").replace(r"\d", "0-9").replace(r"\w", "0-9A-Za-z_") + "]", p)
    # fuori dalle classi: \d -> [0-9] , \w -> [0-9A-Za-z_]  (interpretazione ASCII, vedi caveat nel verdetto)
    p = p.replace(r"\d", "[0-9]").replace(r"\w", "[0-9A-Za-z_]")
    if p.startswith("^"):
        p = p[1:]
    if p.endswith("$") and not p.endswith(r"\$"):
        p = p[:-1]
    return p


def _rep_char(sym):
    """Char rappresentante accettato da un simbolo greenery (Charclass): per positivi il minimo; per negati un char fuori."""
    if not getattr(sym, "negated", False):
        cs = sorted(sym.get_chars())
        return cs[0] if cs else None
    for c in ("~", "#", "!", "0", "a", " ", "\x00"):
        try:
            if sym.accepts(c):
                return c
        except Exception:  # noqa
            pass
    return "~"


def _shortest_string(fsm, cap=100000):
    """Stringa distinguente PIU' CORTA via BFS sul DFA differenza, main-thread e LIMITATA (cap sugli stati visitati):
    niente thread-daemon abbandonati (no leak su server long-lived), nessun hang."""
    from collections import deque
    syms = list(fsm.alphabet)
    seen = {fsm.initial}
    dq = deque([(fsm.initial, "")])
    n = 0
    while dq and n < cap:
        st, path = dq.popleft(); n += 1
        if st in fsm.finals:
            return path
        row = fsm.map.get(st, {})
        for sym in syms:
            t = row.get(sym)
            if t is not None and t not in seen:
                ch = _rep_char(sym)
                if ch is None:
                    continue
                seen.add(t); dq.append((t, path + ch))
    return None


def _accepted_samples(fsm, k=40, cap=20000):
    """Fino a k stringhe ACCETTATE (piu' corte prima) via BFS LIMITATO sul DFA (≤|stati| nodi): veloce, evita la
    lenta greenery .strings() che puo' bloccarsi su FSM grandi."""
    from collections import deque
    syms = list(fsm.alphabet)
    out, seen, dq, n = [], {fsm.initial}, deque([(fsm.initial, "")]), 0
    while dq and n < cap and len(out) < k:
        st, path = dq.popleft(); n += 1
        if st in fsm.finals:
            out.append(path)
        row = fsm.map.get(st, {})
        for sym in syms:
            t = row.get(sym)
            if t is not None and t not in seen:
                ch = _rep_char(sym)
                if ch is None:
                    continue
                seen.add(t); dq.append((t, path + ch))
    return out


def _cross_check_disagreement(r1, r2, f1, n=1500):
    """DIFESA-IN-PROFONDITA' (riduce la fiducia cieca in greenery): greenery dice L(r1)=L(r2); campioniamo stringhe
    (di confine + random) e verifichiamo che Python re NON dia un esito diverso tra r1 e r2. Un disaccordo = infedelta'
    di traduzione/oracolo -> restituisce la stringa colpevole (il gate ABSTIENE invece di firmare un PROVEN dubbio)."""
    import random
    try:
        c1, c2 = _re.compile(r1), _re.compile(r2)
    except Exception:  # noqa
        return None                     # non compilabili in Python re -> niente cross-check (decide greenery)
    chars = set()
    for sym in f1.alphabet:
        if not getattr(sym, "negated", False):
            chars |= set(sym.get_chars())
    pool_chars = sorted(chars) + list("Xx \t#@\n")    # + char 'altri' per sondare oltre l'alfabeto / newline
    if not pool_chars:
        pool_chars = list("ab01")
    rng = random.Random(12345)
    bases = _accepted_samples(f1, k=40)        # seed di confine via BFS limitato (veloce), NON greenery.strings()

    def mut(s):
        if not s:
            return rng.choice(pool_chars)
        i = rng.randint(0, len(s) - 1)
        op = rng.randint(0, 2)
        ch = rng.choice(pool_chars)
        if op == 0:
            return s[:i] + ch + s[i + 1:]
        if op == 1:
            return s[:i] + s[i + 1:]
        return s[:i] + ch + s[i:]

    for _ in range(n):
        if bases and rng.random() < 0.6:
            s = mut(rng.choice(bases))
        else:
            s = "".join(rng.choice(pool_chars) for _ in range(rng.randint(0, 20)))
        try:
            if bool(c1.fullmatch(s)) != bool(c2.fullmatch(s)):
                return s
        except Exception:  # noqa
            pass
    return None


def gate(claim: Claim) -> Verdict:
    try:
        import greenery
    except Exception as e:  # noqa
        return Verdict(Status.ABSTAIN, executed=False, reason=f"greenery non disponibile: {type(e).__name__}")
    p = claim.params or {}
    r1, r2 = p.get("r1"), p.get("r2")
    if not (isinstance(r1, str) and isinstance(r2, str)):
        return Verdict(Status.ABSTAIN, executed=False,
                       reason="mancano r1/r2: le DUE regex (stringhe-pattern) di cui decidere l'equivalenza")
    # ANTI FALSO-PROVEN: \w \W \s \S hanno semantica UNICODE in Python re (\\w matcha lettere accentate) che la
    # traduzione ASCII per automi NON modella -> ABSTAIN, mai un PROVEN falso. (\\d/\\D: ammessi ma con caveat ASCII.)
    if _re.search(r"\\[wWsS]", r1) or _re.search(r"\\[wWsS]", r2):
        return Verdict(Status.ABSTAIN, executed=True,
                       reason="contiene \\w/\\W/\\s/\\S: semantica UNICODE di Python re non modellata fedelmente per "
                              "automi ASCII -> ABSTAIN (non emetto PROVEN falsi).",
                       coverage={"unfaithful_shorthand": True})
    try:
        f1 = greenery.parse(_to_greenery(r1)).to_fsm()
        f2 = greenery.parse(_to_greenery(r2)).to_fsm()
    except Exception as e:  # noqa
        return Verdict(Status.ABSTAIN, executed=True,
                       reason=f"regex fuori dal frammento REGOLARE gestito (backref/lookaround/sintassi): {type(e).__name__}",
                       coverage={"non_regular_or_unsupported": True})

    if f1 == f2:
        # DIFESA-IN-PROFONDITA': prima di firmare PROVEN, cross-check differenziale con Python re (no fiducia cieca in greenery)
        bad = _cross_check_disagreement(r1, r2, f1)
        if bad is not None:
            return Verdict(Status.ABSTAIN, executed=True,
                           reason="greenery li dice EQUIVALENTI ma Python re DISACCORDA su %r -> infedelta' di traduzione/oracolo: "
                                  "ABSTAIN (non firmo un PROVEN dubbio)." % bad,
                           coverage={"cross_check": "FAILED", "disagreement": bad})
        caveat = ("PROVEN sound+COMPLETO per linguaggi REGOLARI (mai 'unknown'); fiducia in greenery (TCB di questo lato), "
                  "corroborata da cross-check differenziale Python re. L(r1)=L(r2) implica la .match-equivalenza.")
        if _re.search(r"\\[dD]", r1) or _re.search(r"\\[dD]", r2):
            caveat += (" NOTA ASCII: \\d/\\D interpretati come [0-9]/[^0-9]; per CIFRE UNICODE il proven NON vale "
                       "(equivalenza relativa all'interpretazione ASCII).")
        return Verdict(Status.CONFIRMED, executed=True,
                       reason="equivalenza di LINGUAGGIO decisa per AUTOMI (FSM ridotti uguali) -> ∀ stringa stesso esito",
                       witness={"equivalent": True, "method": "automata"},
                       reproduce="greenery: parse(r1).to_fsm() == parse(r2).to_fsm()",
                       assurance=PROVEN,
                       coverage={"method": "automata-equivalence (greenery)", "exhaustive": True, "oracle": "greenery-trusted",
                                 "cross_check_diff": "passed (Python re, campione)"},
                       assurance_caveat=caveat)

    # DISTINTE (deciso, sound): la NON-equivalenza e' gia' decisa da f1 != f2. Il TESTIMONE e' best-effort con BUDGET
    # (l'enumerazione .strings() puo' esplodere su FSM grandi -> mai hang: thread con join-timeout).
    diff = f1 ^ f2
    witness = _shortest_string(diff)
    if witness is not None:
        try:
            d1, d2 = bool(_re.fullmatch(r1, witness)), bool(_re.fullmatch(r2, witness))
        except Exception:  # noqa
            d1 = d2 = None
        if d1 is not None and d1 == d2:
            # greenery dice DIVERSI ma il testimone NON distingue sotto Python re -> sospetta infedelta' di traduzione
            # (es. '.'/newline): NON asserire un REFUTED potenzialmente falso -> ABSTAIN onesto.
            return Verdict(Status.ABSTAIN, executed=True,
                           reason="greenery li dice diversi ma il testimone non distingue sotto re.fullmatch "
                                  "(possibile infedelta' di traduzione) -> ABSTAIN, non un REFUTED dubbio",
                           coverage={"witness": witness, "reverify": "non-distinguishing", "suspect": "translation"})
        # CONTROESEMPIO ESEGUITO sotto Python re: SOUND a prescindere da greenery/traduzione (asimmetria cardinale)
        return Verdict(Status.REFUTED, executed=True,
                       reason="regex NON equivalenti: stringa che le distingue, RI-VERIFICATA (controesempio ESEGUITO) con re.fullmatch",
                       witness={"distinguishing_string": witness, "fullmatch_r1": d1, "fullmatch_r2": d2},
                       reproduce="re.fullmatch(r1, w) != re.fullmatch(r2, w)", assurance=PROVEN,
                       coverage={"method": "automata symdiff (greenery), witness ESEGUITO e ri-verificato", "oracle": "executed-counterexample"},
                       assurance_caveat="REFUTED FORTE: controesempio eseguito sotto Python re -> sound anche se greenery/traduzione fossero imperfette.")
    # distinct deciso da greenery ma testimone non estratto entro il budget -> NESSUN controesempio eseguito
    return Verdict(Status.REFUTED, executed=True,
                   reason="regex NON equivalenti (linguaggi diversi, DECISO per automi: FSM ridotti differenti); "
                          "estrazione del testimone oltre il budget -> nessuna stringa esplicita",
                   witness={"equivalent": False, "witness": "budget-exceeded"},
                   reproduce="greenery: parse(r1).to_fsm() != parse(r2).to_fsm()", assurance=PROVEN,
                   coverage={"method": "automata-inequality (greenery)", "oracle": "greenery-trusted", "witness_extraction": "budget-exceeded"},
                   assurance_caveat="REFUTED DEBOLE: NESSUN controesempio eseguito; poggia sulla disuguaglianza greenery "
                                    "(greenery-trusted + fedelta' traduzione), non sull'asimmetria forte.")


def claim_templates(target: str):
    return [Claim(domain="regex_equiv", target=target, kind="equivalence", params={})]


REGEX_EQUIV = Domain(name="regex_equiv", gate=gate, claim_templates=claim_templates,
                     describe="Equivalenza di regex (linguaggi regolari) per AUTOMI: EQUIV->PROVEN | distingue->REFUTED+stringa | non-regolare->ABSTAIN")
register(REGEX_EQUIV)
