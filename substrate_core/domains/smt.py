"""substrate_core.domains.smt — TIER FORMALE: proprieta' UNIVERSALE via SMT (Z3), con ORACOLO FIDATO.

Perche' esiste (il salto oltre l'empirico): in pyprop il prover scrive SIA subject SIA prop -> controlla
l'ORACOLO; il CONFIRMED e' "nessun controesempio in N campioni" (EMPIRICAL) e il residuo oracle-control
(frame-walk / fatti-mentiti) e' IRRIDUCIBILE. Qui invece la proprieta' e' una formula SMT-LIB2 e l'oracolo
e' Z3 (FIDATO, deciso, NON il prover). Il gate verifica  ∃ input: ¬P :
  unsat   -> nessun controesempio -> ∀ input P vale  -> CONFIRMED / assurance=PROVEN (sound sulla teoria decisa)
  sat     -> controesempio (model) RI-VERIFICATO sotto il model -> REFUTED + witness
  unknown -> ABSTAIN(tipato) (frammento indecidibile / timeout)
Niente esecuzione di CODICE non-fidato (solo PARSING d'una formula da parte di Z3) -> niente host-escape ne'
frame-walk: la soundness non dipende da un sandbox, dipende da Z3. NON nel TCB: kernel.py resta puro; z3 vive QUI.
"""
from __future__ import annotations

import re

from ..kernel import Claim, Verdict, Status, Domain, register, PROVEN

# Comandi SMT-LIB2 STATEFUL che SCOLLEGANO la formula mostrata da quella controllata (recon 2026-06-05, red-team):
# (push)(assert FALSE)(pop) o (reset) scartano l'obbligo falsificabile prima che il parser restituisca il vettore
# finale -> resta solo una tautologia -> falso PROVEN firmato. Li RIFIUTIAMO (una proprieta' ∀ legittima non ne ha
# bisogno) E registriamo nel certificato la formula EFFETTIVAMENTE controllata (difesa in profondita').
_SMT_STATEFUL = re.compile(r"\(\s*(push|pop|reset|reset-assertions)\b", re.IGNORECASE)


def _strip_smt_comments(s: str) -> str:
    return re.sub(r";[^\n]*", "", s)


def _free_consts(expr):
    """Costanti uninterpretate (le VARIABILI d'input) referenziate dalla formula -> per il check di non-vacuita'."""
    import z3
    seen, out = set(), []

    def rec(e):
        eid = e.get_id()
        if eid in seen:
            return
        seen.add(eid)
        if z3.is_const(e) and e.decl().kind() == z3.Z3_OP_UNINTERPRETED:
            out.append(e)
        for ch in e.children():
            rec(ch)

    rec(expr)
    return out


def gate(claim: Claim) -> Verdict:
    try:
        import z3
    except Exception as e:  # noqa
        return Verdict(Status.ABSTAIN, executed=False, reason=f"z3 non disponibile: {type(e).__name__}")
    p = claim.params or {}
    smt2 = p.get("property_smt2") or p.get("smt2") or ""
    if not smt2 or not isinstance(smt2, str):
        return Verdict(Status.ABSTAIN, executed=False,
                       reason="manca property_smt2: la PROPRIETA' (claim: vale per OGNI input) come SMT-LIB2")
    if _SMT_STATEFUL.search(_strip_smt_comments(smt2)):
        return Verdict(Status.ABSTAIN, executed=False,
                       reason="SMT-LIB2 con comandi STATEFUL (push/pop/reset): scollegano la formula MOSTRATA da quella "
                              "CONTROLLATA -> RIFIUTATO (anti parse-trick). Una proprieta' ∀ legittima non li usa.",
                       coverage={"rejected": "stateful-smt-commands"})
    try:
        fmls = z3.parse_smt2_string(smt2)        # vettore di asserzioni = la proprieta' P (congiunta)
    except Exception as e:  # noqa
        return Verdict(Status.ABSTAIN, executed=True, reason=f"SMT-LIB2 non parsabile: {type(e).__name__}: {e}")
    if fmls is None or len(fmls) == 0:
        return Verdict(Status.ABSTAIN, executed=True, reason="nessuna asserzione (proprieta' vuota)")
    P = z3.And([f for f in fmls])
    # NON-VACUITA' (duale del check pyprop): la proprieta' deve riferirsi ad almeno UNA variabile d'input.
    # 'true'/'false'/formule chiuse -> nessuna var -> ABSTAIN (niente PROVEN vacuo).
    vars_ = _free_consts(P)
    if not vars_:
        return Verdict(Status.ABSTAIN, executed=True,
                       reason="proprieta' VACUA: nessuna variabile d'input referenziata (no PROVEN triviale)",
                       coverage={"vacuous": True})
    # ORACOLO FIDATO: ∃ input ¬P ? con timeout (totalita': un frammento duro -> unknown -> ABSTAIN, mai hang).
    try:
        to = int(p.get("timeout_ms", 5000))
    except Exception:  # noqa
        to = 5000
    to = max(200, min(to, 30000))
    s = z3.Solver()
    s.set("timeout", to)
    s.add(z3.Not(P))
    r = s.check()
    if r == z3.unsat:
        return Verdict(Status.CONFIRMED, executed=True,
                       reason=f"SMT: UNSAT della negazione -> NESSUN controesempio, ∀ input la proprieta' vale "
                              f"[{len(vars_)} var, oracolo Z3 fidato]",
                       witness={"smt_result": "unsat", "n_vars": len(vars_), "checked_property": str(P)[:1500]},
                       reproduce="z3.Solver(); add(Not(And(asserts))); check()==unsat",
                       assurance=PROVEN,
                       coverage={"method": "SMT(Z3) UNSAT-della-negazione", "exhaustive": True, "oracle": "z3-trusted",
                                 "checked_property": str(P)[:1500]},   # cio' che Z3 ha DAVVERO controllato (anti-divergenza)
                       assurance_caveat=f"PROVEN sound sulla TEORIA decisa da Z3 (es. QF_BV/QF_LIA: complete+sound); "
                                        f"fiducia in Z3 {z3.get_version_string()}. Frammenti indecidibili -> unknown -> ABSTAIN.")
    if r == z3.sat:
        m = s.model()
        wit = {str(d.name()): str(m[d]) for d in m.decls()}
        # RI-VERIFICA del witness: ¬P deve valere SOTTO il model (controesempio SOUND, non solo 'lo dice Z3').
        neg = m.eval(z3.Not(P), model_completion=True)
        if not z3.is_true(neg):
            return Verdict(Status.ABSTAIN, executed=True,
                           reason="model Z3 non ri-verifica ¬P (inatteso) -> ABSTAIN onesto", coverage={"smt_result": "sat-unverified"})
        return Verdict(Status.REFUTED, executed=True,
                       reason="SMT: controesempio TROVATO e RI-VERIFICATO (¬P vale sotto il model) -> proprieta' FALSA",
                       witness={"counterexample": wit, "smt_result": "sat"},
                       reproduce=f"z3: il model {wit} falsifica la proprieta'",
                       assurance=PROVEN,
                       coverage={"method": "SMT(Z3) modello ri-verificato", "oracle": "z3-trusted"})
    return Verdict(Status.ABSTAIN, executed=True,
                   reason=f"SMT: Z3 'unknown' (frammento indecidibile o timeout {to}ms) -> ABSTAIN onesto",
                   coverage={"smt_result": "unknown", "timeout_ms": to})


def claim_templates(target: str):
    return [Claim(domain="smt", target=target, kind="forall_property", params={})]


SMT = Domain(name="smt", gate=gate, claim_templates=claim_templates,
             describe="Proprieta' universale via SMT/Z3 (ORACOLO FIDATO): UNSAT-negazione->PROVEN | model->REFUTED | unknown->ABSTAIN")
register(SMT)
