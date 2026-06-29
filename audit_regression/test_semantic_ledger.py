"""test_semantic_ledger — oracolo assert-based del SEMANTIC LEDGER (raccolto da run_all.py).

Verifica le proprieta' CARDINE, deterministiche e veloci (no corpus, no GPU):
  1. COLLASSO COMPORTAMENTALE: sintassi diverse ma L-equivalenti -> stesso hash E merge backed da CONFIRMED@proven.
  2. BACKDOOR: linguaggio leggermente diverso -> hash diverso, NON merge, giudice REFUTED.
  3. INVARIANTE DI SOUNDNESS: una classe contiene >1 sintassi SOLO se il giudice le conferma; un over-collapse
     (stesso hash, giudice dissente) e' DEMOTATO, mai coniato. Zero falsi-proven nel grafo.
  4. PORTABILITA': .scar verifica OFFLINE (pubkey-only); una corruzione viene RIFIUTATA.
  5. COMPLETEZZA: lookup di una classe presente e di una assente danno prova complete==True.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from substrate_core import verify, Claim, derive_pubkey
from substrate_core.export import load_bundle, verify_bundle
from substrate_core.semantic_hash import semantic_hash
from substrate_core.semantic_ledger import SemanticLedger
from substrate_core.domains import regex_equiv  # noqa: F401

KEY = b"test-semantic-ledger-seed"
PUB = derive_pubkey(KEY)


def _equiv(r1, r2):
    v = verify(Claim(domain="regex_equiv", target="t", kind="equivalence",
                     params={"r1": r1, "r2": r2}), key=KEY)["certificate"]["verdict"]
    return v["status"], v["assurance"]


def test_behavioral_collapse_backed_by_proof():
    led = SemanticLedger(KEY)
    assert led.ingest("a|b")[0] == "new_class"
    assert led.ingest("[ab]")[0] == "collapse_proven", "sintassi diverse L-equivalenti devono collassare"
    assert semantic_hash("a|b") == semantic_hash("[ab]")
    assert led.multi_syntax_classes() == 1
    # il collasso e' backed da un cert CONFIRMED@proven nel grafo write-gated
    assert len(led.graph._certs) >= 1
    for e in led.graph._certs.values():
        vd = e["certificate"]["verdict"]
        assert vd["status"] == "CONFIRMED" and vd["assurance"] == "proven"


def test_backdoor_does_not_collapse():
    assert semantic_hash("[a-z]+") != semantic_hash(r"[a-z.]+"), "linguaggi diversi -> hash diversi (backdoor-sensibile)"
    st, _ = _equiv("[a-z]+", r"[a-z.]+")
    assert st == "REFUTED", "il giudice deve REFUTARE la backdoor con un controesempio eseguito"
    led = SemanticLedger(KEY)
    led.ingest("[a-z]+")
    res = led.ingest(r"[a-z.]+")
    assert res[0] == "new_class", "hash diverso -> nuova classe, NON merge"


def test_soundness_invariant_no_false_proven():
    # ogni classe multi-sintassi e' confermata dal giudice; over-collapse (se esiste) demotato, mai coniato
    led = SemanticLedger(KEY)
    for r in ["a+", "aa*", "(a)+", "a|b", "[ab]", "b|a", "[a-z]+", "x{2}", "xx", "[a-z.]+"]:
        led.ingest(r)
    for h, ms in led.members.items():
        for other in ms[1:]:
            s, asr = _equiv(ms[0], other)
            assert s == "CONFIRMED" and asr == "proven", f"merge non-sound: {ms[0]} / {other} -> {s}/{asr}"
    for e in led.graph._certs.values():           # zero falsi-proven nel grafo
        vd = e["certificate"]["verdict"]
        assert vd["status"] == "CONFIRMED" and vd["assurance"] == "proven"
    # over-collapse esplicito: se collide sull'hash ma il giudice dissente -> DEMOTATO
    a, b = "(.*)", "^([^/]*)(.*)$"
    p = SemanticLedger(KEY)
    p.ingest(a)
    res = p.ingest(b)
    st, asr = _equiv(a, b)
    if semantic_hash(a) == semantic_hash(b) and not (st == "CONFIRMED" and asr == "proven"):
        assert res[0] == "over_collapse_demoted", "over-collapse: hash collide + giudice dissente -> deve DEMOTARE"
        assert b not in p.members[semantic_hash(a)], "l'over-collapse NON deve essere fuso nella classe"


def test_scar_offline_and_corruption_rejected():
    led = SemanticLedger(KEY)
    for r in ["a|b", "[ab]", "x+", "xx*"]:
        led.ingest(r)
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_ledger_test.scar")
    led.export_scar(path)
    b = load_bundle(path)
    assert verify_bundle(b, pubkey=PUB)["intact"] is True, ".scar deve verificare OFFLINE (pubkey-only)"
    if b.get("certs"):
        k0 = next(iter(b["certs"]))
        b["certs"][k0]["sig"] = "00" * 32
        assert verify_bundle(b, pubkey=PUB)["intact"] is False, "una firma corrotta deve essere RIFIUTATA"
    try:
        os.remove(path)
    except OSError:
        pass


def test_completeness_present_and_absent():
    led = SemanticLedger(KEY)
    for r in ["a|b", "[ab]", "x+", "y*"]:
        led.ingest(r)
    assert led.lookup("a|b")["completeness"]["complete"] is True
    ab = led.lookup("###non-esiste###")["completeness"]
    assert ab["complete"] is True and ab.get("absent") is True


if __name__ == "__main__":
    fns = [test_behavioral_collapse_backed_by_proof, test_backdoor_does_not_collapse,
           test_soundness_invariant_no_false_proven, test_scar_offline_and_corruption_rejected,
           test_completeness_present_and_absent]
    for fn in fns:
        fn()
        print(f"  ok {fn.__name__}")
    print(f"test_semantic_ledger: {len(fns)}/{len(fns)} PASS")
