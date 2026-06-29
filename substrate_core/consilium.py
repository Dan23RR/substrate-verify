"""substrate_core.consilium — CONSILIUM-2: fraud-proof off-chain multi-emittente, tier-typed.

FRAMING ONESTO (anti-ASTRA): NON e' swarm-intelligence ne' "intelligenza che si somma". E' IGIENE — una
memoria condivisa multi-agente dove un CONFIRMED FALSO e' MECCANICAMENTE REVERSIBILE PER ESECUZIONE. Quando
due emittenti con CHIAVI e ORACOLI distinti firmano verdetti opposti sullo stesso claim, il substrato NON
vota e NON si fida di nessun oracolo: RI-ESEGUE il witness del REFUTED. Chi ha coniato il CONFIRMED falso e'
smascherato da CHIUNQUE possieda solo le due chiavi PUBBLICHE.

LIMITE DICHIARATO (parte del prodotto): sound SOLO dove il witness e' RI-ESEGUIBILE da terzi indipendenti —
qui il dominio SMT (chiunque abbia Z3 ricontrolla il controesempio). Fuori dal frammento decidibile gli agenti
fanno ABSTAIN e lo sciame ammutolisce. Compone VERDETTI, non SKILL. Vale su 2 nodi e UN dissenso; N agenti e
gli avversari adattivi/collusivi sono EMPIRICAL/ASPIRAZIONE, non gated.

Costruito SOPRA primitivi gia' verdi: Ed25519 conio!=verifica (kernel), CertGraph write-gated (rifiuta
non-firmati), REFUTED-SMT con controesempio ri-verificato (domains/smt), invalidate() su _dependents.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional

from .kernel import Claim, Certificate, Verdict, Status, envelope, verify_sig, cert_from_dict
from .cert_graph import CertGraph
from .domains import smt  # noqa: F401  registra il dominio "smt"


def claim_digest(env: Dict[str, Any]) -> str:
    """Digest STABILE del solo sub-claim: identico tra due certificati con VERDETTI diversi sullo stesso claim
    (il content_hash invece differisce, perche' include il verdict). E' la chiave del 'mercato del disaccordo'."""
    claim = env["certificate"]["claim"]
    s = json.dumps(claim, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def forge_confirmed(claim: Claim, key: bytes, *, reason: str = "(asserito, MAI eseguito dal gate)") -> dict:
    """Un emittente DISONESTO conia un CONFIRMED@proven SENZA eseguire il vero gate: costruisce e FIRMA un
    certificato col proprio seed. La FIRMA e' valida (possiede la chiave); il VERDETTO e' una BUGIA. Il
    substrato NON lo blocca al conio — lo smaschera per RI-ESECUZIONE (e' tutto il punto di CONSILIUM)."""
    cert = Certificate(claim=claim,
                       verdict=Verdict(Status.CONFIRMED, executed=False, reason=reason,
                                       assurance="proven", witness={"asserted": True}),
                       engine="forged-issuer")
    return envelope(cert, key=key)


def forge_refuted(claim: Claim, key: bytes, counterexample: Dict[str, str]) -> dict:
    """Un emittente DISONESTO conia un REFUTED con un controesempio (eventualmente FINTO) per provare a INCASTRARE
    un onesto. La firma e' valida; ma se il controesempio NON ri-esegue, resolve_by_execution NON incastra nessuno
    (no-framing): il witness deve DAVVERO falsificare la proprieta'. Primitivo per i test avversariali."""
    cert = Certificate(claim=claim,
                       verdict=Verdict(Status.REFUTED, executed=False, reason="(REFUTED asserito da avversario)",
                                       assurance="proven", witness={"counterexample": counterexample, "smt_result": "sat"}),
                       engine="forged-issuer")
    return envelope(cert, key=key)


def _reexec_smt_refutation(smt2: str, counterexample: Dict[str, str]) -> bool:
    """RI-ESEGUE il controesempio col SOLO Z3 (indipendente da chi l'ha coniato): True iff Not(P) vale sotto
    l'assegnamento -> il REFUTED e' SOUND. NON legge lo status asserito da nessuno: ricostruisce P e valuta."""
    try:
        import z3
        from .domains.smt import _free_consts
    except Exception:  # noqa
        return False
    try:
        fmls = z3.parse_smt2_string(smt2)
    except Exception:  # noqa
        return False
    if fmls is None or len(fmls) == 0:
        return False
    P = z3.And([f for f in fmls])
    subs = []
    for c in _free_consts(P):
        name = str(c.decl().name())
        if name not in counterexample:
            continue
        val = counterexample[name]
        sort = c.sort()
        try:
            if sort.kind() == z3.Z3_INT_SORT:
                lit = z3.IntVal(int(val))
            elif sort.kind() == z3.Z3_REAL_SORT:
                lit = z3.RealVal(val)
            elif z3.is_bv_sort(sort):
                lit = z3.BitVecVal(int(val), sort.size())
            elif sort.kind() == z3.Z3_BOOL_SORT:
                lit = z3.BoolVal(str(val).lower() == "true")
            else:
                continue
        except Exception:  # noqa
            continue
        subs.append((c, lit))
    try:
        neg = z3.simplify(z3.substitute(z3.Not(P), *subs)) if subs else z3.simplify(z3.Not(P))
        return z3.is_true(neg)
    except Exception:  # noqa
        return False


class Consilium:
    """Memoria condivisa multi-emittente, write-gated dalle firme, con risoluzione-per-esecuzione del dissenso."""

    def __init__(self):
        self.graph = CertGraph()                     # default: rifiuta non-firmati/manomessi (sig incastonata)
        self.by_digest: Dict[str, List[dict]] = {}
        self.unsound: set = set()                    # content_hash QUARANTENATI (UNSOUND, mai sovrascritti)
        self.liars: Dict[str, int] = {}             # pubkey -> n di CONFIRMED falsi coniati

    def ingest(self, env: dict) -> str:
        ch = self.graph.ingest(env)                  # ProvenanceError se non firmato/manomesso
        self.by_digest.setdefault(claim_digest(env), []).append(env)
        return ch

    def detect_dissent(self) -> List[dict]:
        """Claim su cui due emittenti hanno firmato CONFIRMED e REFUTED insieme (il dissenso che conta)."""
        out = []
        for dg, envs in self.by_digest.items():
            statuses = {e["certificate"]["verdict"]["status"] for e in envs}
            if "CONFIRMED" in statuses and "REFUTED" in statuses:
                out.append({"claim_digest": dg, "envs": envs, "claim": envs[0]["certificate"]["claim"]})
        return out

    def resolve_by_execution(self) -> List[dict]:
        """Dirime OGNI dissenso RI-ESEGUENDO il witness del REFUTED (mai per voto/autorita'). Un CONFIRMED su un
        claim il cui REFUTED e' ri-eseguito-sound viene QUARANTENATO UNSOUND e l'emittente loggato come bugiardo."""
        resolutions = []
        for d in self.detect_dissent():
            envs = d["envs"]
            refs = [e for e in envs if e["certificate"]["verdict"]["status"] == "REFUTED"]
            cons = [e for e in envs if e["certificate"]["verdict"]["status"] == "CONFIRMED"]
            claim = d["claim"]
            if claim.get("domain") != "smt":         # fuori dal frammento ri-eseguibile da terzi -> ABSTAIN onesto
                resolutions.append({"claim_digest": d["claim_digest"], "verdict": "ABSTAIN",
                                    "reason": "witness non ri-eseguibile da terzi (dominio non-SMT)"})
                continue
            smt2 = (claim.get("params") or {}).get("property_smt2", "")
            sound_ref = None
            for r in refs:
                wit = (r["certificate"]["verdict"].get("witness") or {}).get("counterexample") or {}
                if _reexec_smt_refutation(smt2, wit):
                    sound_ref = r
                    break
            if sound_ref is None:
                resolutions.append({"claim_digest": d["claim_digest"], "verdict": "UNRESOLVED",
                                    "reason": "nessun controesempio del REFUTED ri-esegue (sospetto)"})
                continue
            for c in cons:                            # il REFUTED e' SOUND -> ogni CONFIRMED qui e' FALSO
                ch = c["content_hash"]
                self.unsound.add(ch)
                self.graph.invalidate(ch)             # propaga la revoca ai dipendenti
                pub = c.get("pubkey")
                self.liars[pub] = self.liars.get(pub, 0) + 1
            resolutions.append({"claim_digest": d["claim_digest"], "verdict": "REFUTED-SOUND",
                                "winner": sound_ref["content_hash"],
                                "quarantined_unsound": [c["content_hash"] for c in cons],
                                "liars": [c.get("pubkey") for c in cons]})
        return resolutions

    def valid_facts(self) -> List[dict]:
        """Fatti validi = tutti gli env TRANNE i quarantenati. Soundness MONOTONA: il falso e' escluso, non
        sovrascritto da un voto (un avversario non puo' ripristinarlo senza un nuovo cert che ri-esegua)."""
        return [e for envs in self.by_digest.values() for e in envs if e["content_hash"] not in self.unsound]


def audit_independently(envs: List[dict], known_pubkeys: List[str]) -> dict:
    """AUDITOR TERZO TRUSTLESS: con SOLO le chiavi PUBBLICHE (mai i seed privati), ri-verifica le firme e
    RI-ESEGUE il witness, raggiungendo lo stesso verdetto DETERMINISTICAMENTE. Nessun terzo fidato."""
    sigs_ok = True
    for e in envs:
        cert = cert_from_dict(e["certificate"])
        pub = e.get("pubkey")
        if pub not in known_pubkeys or not verify_sig(cert, e.get("sig"), pub):
            sigs_ok = False
    ref = next((e for e in envs if e["certificate"]["verdict"]["status"] == "REFUTED"), None)
    verdict = "ABSTAIN"
    if ref is not None:
        claim = ref["certificate"]["claim"]
        smt2 = (claim.get("params") or {}).get("property_smt2", "")
        wit = (ref["certificate"]["verdict"].get("witness") or {}).get("counterexample") or {}
        if _reexec_smt_refutation(smt2, wit):
            verdict = "REFUTED-SOUND"
    return {"sigs_ok": sigs_ok, "independent_verdict": verdict}


# --- proprieta' SMT per il gate: claim-1 VERA (consenso banale), claim-2 FALSA (un emittente mente) ---
PROP_TRUE = "(declare-const x Int)(assert (=> (> x 0) (> (+ x 1) 0)))"      # ∀x>0: x+1>0  -> CONFIRMED
PROP_FALSE = "(declare-const x Int)(assert (> (* x x) 0))"                  # ∀x: x²>0  -> FALSO a x=0


def consilium2(verbose: bool = True) -> Dict[str, bool]:
    """CONSILIUM-2: il piu' piccolo sciame onesto (no-GPU, no-LLM). Ritorna i 3 assert del cancello."""
    from .kernel import verify, derive_pubkey
    KEY_A, KEY_B = b"consilium-issuer-A", b"consilium-issuer-B"
    PUB_A, PUB_B = derive_pubkey(KEY_A), derive_pubkey(KEY_B)
    assert PUB_A != PUB_B

    claim1 = Claim(domain="smt", target="claim1", kind="forall_property", params={"property_smt2": PROP_TRUE})
    claim2 = Claim(domain="smt", target="claim2", kind="forall_property", params={"property_smt2": PROP_FALSE})

    # claim-1: ENTRAMBI onesti (gate reale) -> stesso verdetto deterministico (consenso banale, nessun mercato)
    a1 = verify(claim1, key=KEY_A)
    b1 = verify(claim1, key=KEY_B)
    # claim-2: A MENTE (conia CONFIRMED senza eseguire) ; B onesto (gate reale) -> REFUTED + controesempio
    a2 = forge_confirmed(claim2, KEY_A)
    b2 = verify(claim2, key=KEY_B)

    c = Consilium()
    for e in (a1, b1, a2, b2):
        c.ingest(e)

    # ASSERT-1: dissenso ESATTAMENTE su claim-2, ZERO su claim-1
    dissent = c.detect_dissent()
    a1_ok = (len(dissent) == 1 and dissent[0]["claim_digest"] == claim_digest(b2)
             and dissent[0]["claim_digest"] != claim_digest(b1))

    # ASSERT-2: risoluzione per ESECUZIONE -> A quarantenato UNSOUND, B resta valido, A loggato bugiardo
    res = c.resolve_by_execution()
    a2_ok = (len(res) == 1 and res[0]["verdict"] == "REFUTED-SOUND"
             and a2["content_hash"] in c.unsound
             and b2["content_hash"] not in c.unsound
             and c.liars.get(PUB_A) == 1 and PUB_B not in c.liars)

    # ASSERT-3: auditor terzo con SOLE 2 pubkey -> stesso verdetto deterministico + soundness monotona
    aud = audit_independently([a2, b2], known_pubkeys=[PUB_A, PUB_B])
    valid_hashes = {e["content_hash"] for e in c.valid_facts()}
    a3_ok = (aud["sigs_ok"] and aud["independent_verdict"] == "REFUTED-SOUND"
             and a2["content_hash"] not in valid_hashes        # falso ESCLUSO
             and b2["content_hash"] in valid_hashes)           # vero RESTA

    if verbose:
        print(f"  claim-1 (vera):  A={a1['certificate']['verdict']['status']} "
              f"B={b1['certificate']['verdict']['status']}  -> consenso deterministico")
        print(f"  claim-2 (falsa): A=CONFIRMED(FORGIATO) B={b2['certificate']['verdict']['status']}"
              f"+witness={(b2['certificate']['verdict'].get('witness') or {}).get('counterexample')}")
        print(f"  [ASSERT-1] dissenso solo su claim-2, zero su claim-1 = {a1_ok}")
        print(f"  [ASSERT-2] A quarantenato UNSOUND per ri-esecuzione, B valido, A=bugiardo = {a2_ok}")
        print(f"  [ASSERT-3] auditor terzo (sole 2 pubkey) converge + soundness monotona = {a3_ok}")
    return {"assert1": a1_ok, "assert2": a2_ok, "assert3": a3_ok}


def main() -> int:
    print("=== CONSILIUM-2 (fraud-proof multi-emittente, dominio SMT) ===")
    g = consilium2(verbose=True)
    ok = all(g.values())
    n = sum(g.values())
    print(f"\nCONSILIUM-2: GATE GREEN ({n}/3)" if ok else f"\nCONSILIUM-2: GATE FAILED ({n}/3)")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
