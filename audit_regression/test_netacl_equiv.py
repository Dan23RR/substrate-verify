"""test_netacl_equiv — oracolo assert-based del 3o dominio (firewall/ACL equivalence) + NetAclLedger.

Deterministico, veloce (z3, no GPU, no net). Verifica: CONFIRMED (equivalenti), REFUTED+pacchetto RI-ESEGUITO
dalla semantica indipendente (asimmetria cardinale), REFUTED shadowing-aware (first-match), ABSTAIN fuori
frammento (cardinal-hole chiusa), backdoor MAI collassata, e le 5 proprieta' del ledger (collasso solo via
CONFIRMED@proven, backdoor separata, zero falsi-proven, .scar offline + corruzione rifiutata, completezza).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from substrate_core import verify, Claim, derive_pubkey
from substrate_core.export import load_bundle, verify_bundle
from substrate_core.domains.netacl_equiv import decision_py
from substrate_core.netacl_hash import netacl_semantic_hash
from substrate_core.netacl_ledger import NetAclLedger

KEY = b"test-netacl-seed"
PUB = derive_pubkey(KEY)
F = {"src": 8, "dport": 16}


def _gate(A, B, da="DENY", db="DENY", fields=F):
    e = verify(Claim(domain="netacl_equiv", target="t", kind="equivalence",
                     params={"rulesetA": A, "rulesetB": B, "fields": fields, "defaultA": da, "defaultB": db}), key=KEY)
    v = e["certificate"]["verdict"]
    return v["status"], v["assurance"], v.get("witness", {}) or {}


# rulesets di riferimento
EQ_A = [{"match": {"src": [10, 20]}, "action": "ALLOW"}]
EQ_B = [{"match": {"src": [10, 15]}, "action": "ALLOW"}, {"match": {"src": [16, 20]}, "action": "ALLOW"}]
BACKDOOR = [{"match": {"src": [10, 20]}, "action": "ALLOW"}, {"match": {"src": [200, 200]}, "action": "ALLOW"}]


def test_confirmed_equivalent_range_split():
    s, a, _ = _gate(EQ_A, EQ_B)
    assert s == "CONFIRMED" and a == "proven", f"split di range equivalente deve essere CONFIRMED@proven, non {s}/{a}"


def test_refuted_backdoor_packet_reexecuted():
    A = [{"match": {"dport": [80, 80]}, "action": "ALLOW"}]
    B = [{"match": {"dport": [80, 81]}, "action": "ALLOW"}]
    s, a, w = _gate(A, B)
    assert s == "REFUTED" and a == "proven"
    pkt = w["packet"]
    # ASIMMETRIA CARDINALE: il pacchetto e' RI-ESEGUITO dalla semantica INDIPENDENTE (non asserito da z3)
    assert decision_py(A, "DENY", pkt) == "DENY" and decision_py(B, "DENY", pkt) == "ALLOW"
    assert "BACKDOOR" in w["direction"]


def test_refuted_shadowing_first_match():
    A = [{"match": {"dport": [22, 22]}, "action": "DENY"}, {"match": {"dport": [1, 100]}, "action": "ALLOW"}]
    B = [{"match": {"dport": [1, 100]}, "action": "ALLOW"}]
    s, a, w = _gate(A, B)
    assert s == "REFUTED", "il deny-override first-match deve essere modellato, non appiattito"
    pkt = w["packet"]
    assert decision_py(A, "DENY", pkt) == "DENY" and decision_py(B, "DENY", pkt) == "ALLOW"


def test_abstain_out_of_fragment():
    A = [{"match": {"flags": [2, 2]}, "action": "ALLOW"}]   # 'flags' NON dichiarato nello schema
    s, a, _ = _gate(A, EQ_B)
    assert s == "ABSTAIN", "un campo fuori schema NON deve mai raggiungere un verdetto (cardinal-hole chiusa)"


def test_backdoor_never_collapses():
    # IL PUNTO: il fingerprint e' un bucketer a campione -> PUO' collidere su un backdoor 'raro' (qui src=200,
    # non campionato). NON e' un buco di soundness: il GIUDICE z3 lo REFUTA comunque. La soundness e' del giudice.
    s, _, w = _gate(EQ_A, BACKDOOR)
    assert s == "REFUTED", "due rulesets diversi devono essere REFUTATI dal giudice (anche se l'hash collide)"
    pkt = w["packet"]
    assert decision_py(EQ_A, "DENY", pkt) != decision_py(BACKDOOR, "DENY", pkt)   # controesempio eseguito


def test_canonical_hash_equal_for_equivalent_syntaxes():
    assert netacl_semantic_hash(EQ_A, F, "DENY") == netacl_semantic_hash(EQ_B, F, "DENY"), \
        "rulesets equivalenti -> stesso fingerprint (equivalente => stesse risposte sul campione)"


def test_ledger_collapse_and_soundness():
    led = NetAclLedger(KEY)
    assert led.ingest("acl_v1", EQ_A, F)[0] == "new_class"
    assert led.ingest("acl_v2_refactor", EQ_B, F)[0] == "collapse_proven", "refactor equivalente deve collassare via z3"
    # la backdoor collide sul fingerprint (src=200 non campionato) MA il giudice la REFUTA -> DEMOTATA, MAI fusa
    bd = led.ingest("acl_backdoor", BACKDOOR, F)[0]
    assert bd in ("new_class", "over_collapse_demoted") and bd != "collapse_proven", \
        f"la backdoor non deve MAI collassare (esito {bd})"
    assert "acl_backdoor" not in led.members[netacl_semantic_hash(EQ_A, F, "DENY")], "backdoor NON nella classe equivalente"
    assert led.multi_member_classes() == 1                      # solo EQ_A+EQ_B
    if bd == "over_collapse_demoted":
        assert len(led.near_misses) >= 1                        # l'over-collapse e' loggato col pacchetto, mai coniato
    # zero falsi-proven: ogni cert nel grafo e' CONFIRMED@proven
    for e in led.graph._certs.values():
        vd = e["certificate"]["verdict"]
        assert vd["status"] == "CONFIRMED" and vd["assurance"] == "proven"
    assert led.graph.verify_integrity(pubkey=PUB)["intact"] is True


def test_ledger_scar_offline_and_corruption():
    led = NetAclLedger(KEY)
    led.ingest("a", EQ_A, F)
    led.ingest("b", EQ_B, F)
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_netacl_test.scar")
    led.export_scar(path)
    b = load_bundle(path)
    assert verify_bundle(b, pubkey=PUB)["intact"] is True
    if b.get("certs"):
        k0 = next(iter(b["certs"]))
        b["certs"][k0]["sig"] = "00" * 32
        assert verify_bundle(b, pubkey=PUB)["intact"] is False
    led2 = NetAclLedger(KEY)
    led2.ingest("a", EQ_A, F)
    lk = led2.lookup(EQ_A, F)
    assert lk["completeness"]["complete"] is True
    ab = led2.lookup([{"match": {"src": [99, 99]}, "action": "ALLOW"}], F)
    assert ab["completeness"]["complete"] is True
    try:
        os.remove(path)
    except OSError:
        pass


if __name__ == "__main__":
    fns = [test_confirmed_equivalent_range_split, test_refuted_backdoor_packet_reexecuted,
           test_refuted_shadowing_first_match, test_abstain_out_of_fragment, test_backdoor_never_collapses,
           test_canonical_hash_equal_for_equivalent_syntaxes, test_ledger_collapse_and_soundness,
           test_ledger_scar_offline_and_corruption]
    for fn in fns:
        fn()
        print(f"  ok {fn.__name__}")
    print(f"test_netacl_equiv: {len(fns)}/{len(fns)} PASS")
