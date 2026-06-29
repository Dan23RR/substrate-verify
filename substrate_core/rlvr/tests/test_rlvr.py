"""Gate eseguito di substrate_core.rlvr — ogni claim del loup no-GPU ha qui il suo test.

Disciplina: REFUTED=esistenziale=sound; CONFIRMED=oracle-bound; falso-proven == peccato cardinale (mai).
Run:  python -m pytest substrate_core/rlvr/tests/test_rlvr.py -q
"""
from substrate_core.rlvr.oracle import verify_equiv
from substrate_core.rlvr.quality import ast_nodes, is_identity, syntactic_len
from substrate_core.rlvr.reward import reward
from substrate_core.rlvr.factory import build_split, abstain_catalog, TRAIN_RULES, HOLDOUT_RULES
from substrate_core.rlvr.pregate import build_pregate_holdout, score_pregate, extract_regex
from substrate_core.rlvr.dpo_builder import build_dpo_pairs, audit_pairs, format_answer
from substrate_core.rlvr.evaluator import evaluate, parse_tier, parse_conf, expected_calibration_error
from substrate_core.rlvr.protocol import protocol_hash, PROTOCOL
from substrate_core.rlvr.compare import summarize, DEATH_THRESHOLD_PP


# ----------------------------------------------------------------------- oracle
def test_oracle_three_way_and_empty_witness():
    assert verify_equiv("a+", "aa*")["status"] == "CONFIRMED"
    assert verify_equiv("a+", "aa*")["assurance"] == "proven"
    r = verify_equiv("a+", "a*")
    assert r["status"] == "REFUTED" and r["assurance"] == "proven"
    assert r["witness"] == "", "la STRINGA VUOTA e' un witness reale, non assente"
    assert verify_equiv("a+", "b+")["witness"] == "b"
    assert verify_equiv(r"\w+", r"\w+")["status"] == "ABSTAIN"   # unicode-shorthand


# ---------------------------------------------------------------------- quality
def test_ast_nodes_ranks_where_char_len_inverts():
    assert ast_nodes("a{10}") < ast_nodes("aaaaaaaaaa")     # 4 < 22  (len(char) inverte: 5 < 10? no: 5<10 ok ma..)
    assert syntactic_len("a{10}") < syntactic_len("aaaaaaaaaa")  # char-len: 5 < 10 (qui non aiuta a distinguere)
    assert ast_nodes("a") < ast_nodes("(((a)))")            # 4 < 13  penalizza grouping ridondante
    assert ast_nodes("a{1,3}") < ast_nodes("a|aa|aaa")      # 4 < 16  penalizza alternation espansa
    assert ast_nodes(r"a\1") is None or isinstance(ast_nodes(r"a\1"), int)  # non-parsabile -> None, mai crash


# ----------------------------------------------------------------------- reward
def test_reward_non_saturable_and_no_false_proven():
    rw = lambda a, b: reward(a, b)["reward"]
    assert rw("a+", "a+") == 0.0,            "identita' -> 0 (crepa #1)"
    assert rw("(((a)))", "a") == 1.0,        "de-parenthesize e' semplificazione GENUINA -> premiata"
    assert rw("aaaaaaaaaa", "a{10}") == 1.0, "piu' semplice dove i char invertono"
    assert rw("a|aa|aaa", "a{1,3}") == 1.0,  "collassa alternation"
    assert rw("a+", "aa*") == 0.0,           "equivalente ma NON piu' semplice"
    assert rw("a+", "b+") == 0.0,            "REFUTED -> 0"
    assert rw(r"\w+", r"\w+") == 0.0,        "ABSTAIN unicode -> 0, mai proven"
    r = reward("a|aa|aaa", "a{1,3}")
    assert r["tier_sound"] == "proven" and r["tier_quality"] == "empirical" and r["tier"] == "empirical"


# ---------------------------------------------------------------------- factory
def test_algebraic_difficulty_no_copy_shortcut():
    # difficolta' 2+ = riconoscimento di ripetizioni: la simplificazione NON e' copiabile da un sotto-termine
    recs = build_split(40, seed=0, split="train", difficulty=2)
    A = [r for r in recs if r["channel"] == "A"]
    assert A
    assert all(reward(r["prompt_regex"], r["completion"])["reward"] == 1.0 for r in A)  # self-check
    assert all(r["completion"] not in r["prompt_regex"] for r in A)                     # NIENTE shortcut di copia
    assert all(r.get("rule") in ("plus", "count", "countadd", "countrange") for r in A)


def test_factory_self_checking_and_disjoint_rules():
    train = build_split(80, seed=0, split="train")
    hold = build_split(30, seed=10000, split="holdout")
    A = [r for r in train if r["channel"] == "A"]
    B = [r for r in train if r["channel"] == "B"]
    C = [r for r in train if r["channel"] == "C"]
    assert A and B and C
    # ogni A e' una semplificazione reale (reward 1.0 ri-verificato live)
    assert all(reward(r["prompt_regex"], r["completion"])["reward"] == 1.0 for r in A)
    # ogni B e' REFUTED (rejected sound)
    assert all(verify_equiv(r["prompt_regex"], r["completion"])["status"] == "REFUTED" for r in B)
    # canale C: tutti ABSTAIN, copre unicode + non-regolari
    assert all(r["got_status"] == "ABSTAIN" for r in C)
    notes = " ".join(r["note"] for r in C)
    for tok in [r"\w", r"\W", r"\s", r"\S", "backref", "lookahead"]:
        assert tok in notes
    # zero falsi-proven ovunque
    assert all(reward(r["prompt_regex"], r["completion"])["tier_sound"] == "proven" for r in A)
    # regole train/holdout DISGIUNTE (anti-overfit, crepa #5)
    rtr = {r.get("rule") for r in A}
    rho = {r.get("rule") for r in hold if r["channel"] == "A"}
    assert rtr.issubset(set(TRAIN_RULES)) and rho.issubset(set(HOLDOUT_RULES)) and rtr.isdisjoint(rho)


# ---------------------------------------------------------------------- pregate (esperimento #0)
def test_pregate_scoring_and_extractor():
    assert extract_regex("Simplified: `a+`") == "a+"
    assert extract_regex("```regex\na{1,3}\n```") == "a{1,3}"
    assert extract_regex("result = a|b") == "a|b"
    assert extract_regex("`(a|b)` poi `c+`") == "c+"      # prende l'ULTIMO backtick
    assert extract_regex("") is None
    # junk di formattazione dei modelli Coder (fence ```lang e annidati) — visti in run reale
    assert extract_regex("```csharp\n`c*bc?bb+`\n```") == "c*bc?bb+"
    assert extract_regex("````regex\n(a*)\n```") == "(a*)"
    assert extract_regex("```python\na|b|c\n```") == "a|b|c"
    items = build_pregate_holdout(30, seed=777)
    gold = {it["id"]: ["`%s`" % it["gold"]] for it in items}
    g = score_pregate(items, gold, k=8)
    assert g["pass@1"] == 1.0 and g["project_falsified_zero_gpu"] is False
    junk = {it["id"]: ["non lo so"] for it in items}
    j = score_pregate(items, junk, k=8)
    assert j["pass@1"] == 0.0 and j["project_falsified_zero_gpu"] is True
    ident = {it["id"]: ["`%s`" % it["bloated"]] for it in items}   # copia dell'input
    assert score_pregate(items, ident, k=8)["pass@1"] == 0.0       # identita' non conta (crepa #1)


# -------------------------------------------------------------------- dpo builder
def test_dpo_witness_conditioned():
    pairs = build_dpo_pairs(80, seed=0)
    au = audit_pairs(pairs)
    assert au["chosen_equals_rejected"] == 0
    assert au["with_injected_witness"] >= 1   # la distinguishing_string compare nel rejected
    assert au["calibration_abstain"] >= 1     # coppie di calibrazione ABSTAIN presenti
    # ogni coppia di tipo (ii) ha rejected = identita' (copia dell'input) -> colpisce crepa #1
    ii = [p for p in pairs if p["type"] == "ii_identity"]
    assert ii and all("copia dell'input" in p["rejected"] for p in ii)


def test_dpo_no_proven_tag_prevents_abstain_collapse():
    # nessuna coppia DPO deve taggare 'proven' (causava il collasso su abstain). Solo empirical/abstain.
    pairs = build_dpo_pairs(60, seed=0)
    for p in pairs:
        assert "<tier>proven</tier>" not in p["chosen"], p["type"]
        assert "<tier>proven</tier>" not in p["rejected"], p["type"]
    # abstain compare SOLO nelle coppie di calibrazione (chosen)
    assert all("<tier>abstain</tier>" not in p["chosen"]
               for p in pairs if p["type"] != "iii_calibration_abstain")


def test_dpo_plain_ablation_strips_witness():
    plain = build_dpo_pairs(80, seed=0, inject_witness=False)
    ap = audit_pairs(plain)
    assert ap["with_injected_witness"] == 0, "B_plain non deve contenere witness (ablazione)"
    assert ap["chosen_equals_rejected"] == 0 and ap["calibration_abstain"] >= 1
    # stesse coppie ma B_witness DEVE contenere witness -> l'unica differenza e' il witness
    wit = build_dpo_pairs(80, seed=0, inject_witness=True)
    assert audit_pairs(wit)["with_injected_witness"] >= 1
    assert len(plain) == len(wit), "stesso numero di coppie: isola la sola variabile witness"


# ---------------------------------------------------------------------- evaluator
def _eval_items_and_gold():
    hold = build_split(30, seed=10000, split="holdout")
    items, gold = [], {}
    for r in hold:
        if r["channel"] == "A":
            items.append({"id": r["task_id"], "bloated": r["prompt_regex"], "gold": r["completion"]})
            gold[r["task_id"]] = format_answer(r["completion"], "empirical")
        elif r["channel"] == "C":
            iid = "C-" + r["prompt_regex"]
            items.append({"id": iid, "bloated": r["prompt_regex"], "expected_status": "ABSTAIN"})
            gold[iid] = format_answer(r["completion"], "abstain")
    return items, gold


def test_evaluator_gold_perfect():
    items, gold = _eval_items_and_gold()
    g = evaluate(items, gold)
    assert g["solve_rate_genuino"] == 1.0
    assert g["false_proven_count"] == 0 and g["false_proven_violation"] is False
    assert g["abstain_recall"] == 1.0
    assert g["tier_reliability"]["abstain"]["accuracy"] == 1.0
    assert g["ece"] is None and g["ece_measurable"] is False  # niente <conf> emessa -> onesto: non misurabile


def test_evaluator_catches_false_proven_on_abstain():
    items, gold = _eval_items_and_gold()
    bad = dict(gold)
    ckey = next(it["id"] for it in items if it.get("expected_status") == "ABSTAIN")
    cbloat = next(it["bloated"] for it in items if it["id"] == ckey)
    bad[ckey] = format_answer(cbloat, "proven")   # dichiara proven su un caso unicode ABSTAIN
    b = evaluate(items, bad)
    assert b["false_proven_count"] >= 1 and b["false_proven_violation"] is True


def test_ece_utility_semantics():
    # (conf=0, correct=True) = "0% confidente ma giusto" = MASSIMA miscalibrazione = ECE 1.0
    assert expected_calibration_error([(0.0, True), (0.0, True)]) == 1.0
    # confidenza che combacia con l'accuratezza = ECE 0
    assert expected_calibration_error([(1.0, True), (1.0, True)]) == 0.0
    assert parse_conf("`a`\n<tier>proven</tier> <conf>0.9</conf>") == 0.9
    assert parse_conf("`a`\n<tier>proven</tier>") is None


# ----------------------------------------------------------------------- protocol
def test_protocol_frozen_and_retires_overclaims():
    assert protocol_hash() == protocol_hash()           # deterministico
    assert PROTOCOL["death_threshold_pp"] == 5.0
    assert any("cert-algebra" in c for c in PROTOCOL["retired_claims"])
    assert any("vaporware" in c for c in PROTOCOL["retired_claims"])


# ------------------------------------------------------------------- compare (cancello §8)
def _rep(bracket, seed, solve, fp=0, abst=1.0, aurc=0.05):
    return {"bracket": bracket, "seed": seed, "solve_rate_genuino": solve, "false_proven_count": fp,
            "abstain_recall": abst, "risk_coverage": {"aurc": aurc}}


def test_compare_witness_effect_and_thesis_logic():
    # witness batte plain di 8pp su 3 seed, zero falsi-proven -> tesi SUPPORTATA
    reps = []
    for s in (0, 1, 2):
        reps += [_rep("A_control", s, 0.90), _rep("B_plain_dpo", s, 0.85), _rep("B_witness_dpo", s, 0.93)]
    out = summarize(reps)
    assert round(out["witness_effect_pp"], 1) == 8.0
    assert out["any_false_proven"] is False
    assert out["thesis_supported"] is True

    # effetto < 5pp -> tesi FALSIFICATA
    reps2 = []
    for s in (0, 1, 2):
        reps2 += [_rep("B_plain_dpo", s, 0.90), _rep("B_witness_dpo", s, 0.92)]
    assert summarize(reps2)["thesis_supported"] is False

    # un solo falso-proven -> vincolo duro violato -> tesi NON supportata anche se l'effetto e' grande
    reps3 = [_rep("B_plain_dpo", 0, 0.80), _rep("B_witness_dpo", 0, 0.95, fp=1)]
    s3 = summarize(reps3)
    assert s3["any_false_proven"] is True and s3["thesis_supported"] is False

    # manca il bracket B -> INCOMPLETO (None), non un falso verdetto
    assert summarize([_rep("A_control", 0, 0.96)])["thesis_supported"] is None
    assert DEATH_THRESHOLD_PP == 5.0
