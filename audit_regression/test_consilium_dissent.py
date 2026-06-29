"""Acceptance: CONSILIUM-2 — fraud-proof off-chain multi-emittente risolto PER ESECUZIONE (dominio SMT).

Entra nel gate gated (run_all.py auto-scopre i test_*.py). Verifica che:
 (1) il dissenso CONFIRMED-vs-REFUTED e' rilevato solo sul claim conteso;
 (2) il falso CONFIRMED e' quarantenato UNSOUND RI-ESEGUENDO il witness (mai per voto/autorita');
 (3) un auditor terzo con SOLE le pubkey converge deterministicamente; soundness MONOTONA;
 (4) ANTI-FRAMING: un avversario che forgia un REFUTED con controesempio FINTO NON incastra l'onesto;
 (5) il resolver IGNORA lo status asserito (un CONFIRMED falso con executed=True e' comunque smascherato).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from substrate_core.kernel import verify, Claim, derive_pubkey
from substrate_core.consilium import (
    Consilium, consilium2, forge_confirmed, forge_refuted, audit_independently,
    claim_digest, PROP_TRUE, PROP_FALSE,
)

KEY_A, KEY_B = b"consilium-issuer-A", b"consilium-issuer-B"
PUB_A, PUB_B = derive_pubkey(KEY_A), derive_pubkey(KEY_B)


def test_core_three_asserts():
    g = consilium2(verbose=False)
    assert g["assert1"], "ASSERT-1 (dissenso solo sul claim conteso) fallito"
    assert g["assert2"], "ASSERT-2 (quarantena per ri-esecuzione) fallito"
    assert g["assert3"], "ASSERT-3 (auditor terzo trustless + soundness monotona) fallito"


def test_resolver_ignores_asserted_status():
    # A conia un CONFIRMED falso ma con executed=True (prova a sembrare legittimo): deve essere smascherato lo stesso,
    # perche' il resolver RI-ESEGUE il witness del REFUTED e NON legge lo status/flag asserito da A.
    claim2 = Claim(domain="smt", target="c2", kind="forall_property", params={"property_smt2": PROP_FALSE})
    a2 = forge_confirmed(claim2, KEY_A, reason="(finge executed)")
    a2["certificate"]["verdict"]["executed"] = True   # A bara anche sul flag
    # NB: cambiare il corpo invalida la firma -> il write-gate del grafo DEVE rifiutarlo (difesa in profondita').
    c = Consilium()
    rejected = False
    try:
        c.ingest(a2)
    except Exception:
        rejected = True
    assert rejected, "un corpo manomesso post-firma DEVE essere rifiutato dal write-gate"

    # versione corretta: A firma onestamente un cert il cui VERDETTO e' la bugia (executed=False, ma CONFIRMED falso)
    a2b = forge_confirmed(claim2, KEY_A)
    b2 = verify(claim2, key=KEY_B)
    c2 = Consilium()
    c2.ingest(a2b); c2.ingest(b2)
    res = c2.resolve_by_execution()
    assert res and res[0]["verdict"] == "REFUTED-SOUND"
    assert a2b["content_hash"] in c2.unsound and b2["content_hash"] not in c2.unsound


def test_anti_framing_fake_counterexample():
    # Claim VERO (∀x>0: x+1>0). B onesto -> CONFIRMED. A forgia un REFUTED con controesempio FINTO (x=5).
    # resolve_by_execution RI-ESEGUE: Not(P) a x=5 e' FALSO -> il controesempio non regge -> A NON incastra B.
    claim1 = Claim(domain="smt", target="c1", kind="forall_property", params={"property_smt2": PROP_TRUE})
    b1 = verify(claim1, key=KEY_B)
    assert b1["certificate"]["verdict"]["status"] == "CONFIRMED"
    a1_fake = forge_refuted(claim1, KEY_A, counterexample={"x": "5"})   # x=5 NON falsifica x>0=>x+1>0
    c = Consilium()
    c.ingest(b1); c.ingest(a1_fake)
    res = c.resolve_by_execution()
    assert res and res[0]["verdict"] == "UNRESOLVED", "un controesempio finto NON deve risolvere nulla"
    # l'onesto B resta VALIDO: nessun framing
    valid = {e["content_hash"] for e in c.valid_facts()}
    assert b1["content_hash"] in valid, "l'agente onesto NON deve essere incastrato da un witness finto"
    assert PUB_A not in c.liars or c.liars.get(PUB_A, 0) == 0


def test_independent_auditor_needs_no_secret():
    claim2 = Claim(domain="smt", target="c2", kind="forall_property", params={"property_smt2": PROP_FALSE})
    a2 = forge_confirmed(claim2, KEY_A)
    b2 = verify(claim2, key=KEY_B)
    aud = audit_independently([a2, b2], known_pubkeys=[PUB_A, PUB_B])
    assert aud["sigs_ok"] and aud["independent_verdict"] == "REFUTED-SOUND"
    # un auditor con la pubkey SBAGLIATA non valida le firme (no fiducia cieca)
    bad = audit_independently([a2, b2], known_pubkeys=[derive_pubkey(b"qualcun-altro")])
    assert not bad["sigs_ok"]


if __name__ == "__main__":
    test_core_three_asserts()
    test_resolver_ignores_asserted_status()
    test_anti_framing_fake_counterexample()
    test_independent_auditor_needs_no_secret()
    print("test_consilium_dissent: ALL PASS (dissenso risolto per esecuzione, anti-framing, auditor trustless)")
