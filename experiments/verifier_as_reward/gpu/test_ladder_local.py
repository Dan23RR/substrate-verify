"""Local CPU smoke test for modal_ladder.py pure logic (no modal, no GPU needed).
Run:  python experiments/verifier_as_reward/gpu/test_ladder_local.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import modal_ladder as ml

fails = []
def check(name, cond, info=""):
    print(("PASS  " if cond else "FAIL  ") + name + (f"   [{info}]" if info != "" else ""))
    if not cond: fails.append(name)

# 1. verifier reward: correct == 1.0 > hack (capped ~0.5) > invalid == 0
vr = ml.make_reward("verifier")
r = vr(["(ab)*", "|ab|abab", "((("], target=["(ab)*"] * 3)
check("verifier: correct == 1.0", abs(r[0] - 1.0) < 1e-9, r)
check("verifier: hack < 1.0", r[1] < 0.999, r)
check("verifier: hack still gets dense signal (>0.4)", r[1] > 0.4, r)
check("verifier: invalid == 0.0", r[2] == 0.0, r)

# 2. bounded L=2: a bounded-hack (right up to L, wrong beyond) MAXES the reward — by design
br = ml.make_reward("bounded", 2)
r2 = br(["a*", "|a|aa", "b*"], target=["a*"] * 3)
check("bounded2: true regex == 1.0", abs(r2[0] - 1.0) < 1e-9, r2)
check("bounded2: bounded-hack == 1.0 (the gap is the unverified region)", abs(r2[1] - 1.0) < 1e-9, r2)
check("bounded2: clearly-wrong < 1.0", r2[2] < 0.999, r2)

# 3. classify: factorized outcome + first-divergence length
c = ml.classify("|a|aa", "a*", P=["", "a", "aa"], N=["b", "ab"])
check("classify: parses", c["parse"])
check("classify: example-consistent (fits shown P/N)", c["ex_cons"])
check("classify: NOT equivalent", not c["eq"])
check("classify: bounded-consistent@2", c["bcons"]["2"])
check("classify: NOT bounded-consistent@4", not c["bcons"]["4"])
check("classify: first divergence at length 3 ('aaa')", c["first_div"] == 3, c["first_div"])
c2 = ml.classify("a*", "a*", P=["", "a"], N=["b"])
check("classify: equivalent => eq=True, first_div=None", c2["eq"] and c2["first_div"] is None)

# 4. judge reward: memorization hack maxes it; nothing can beat it
jr = ml.make_reward("judge")
r3 = jr(["|ab|abab", "(ab)*"], pos=[["", "ab", "abab"]] * 2, neg=[["a", "b", "aab"]] * 2)
check("judge: memorization hack == 1.0", abs(r3[0] - 1.0) < 1e-9, r3)
check("judge: true regex cannot exceed the hack", r3[1] <= r3[0] + 1e-9, r3)

# 5. parse control: 1/0 on validity, no semantics
pr = ml.make_reward("parse")
r4 = pr(["a*", "((("])
check("parse: valid=1.0 / invalid=0.0", r4 == [1.0, 0.0], r4)

# 6. aggregate + E3 best-of-n selectors
g = [ml.classify(rx, "(ab)*", P=["", "ab"], N=["a", "b"]) for rx in ["|ab|abab", "(ab)*", "a*", "((("]]
m = ml.aggregate([g])
check("agg: pass@k == 1 (one correct in group)", m["pass_at_k"] == 1.0, m["pass_at_k"])
check("agg: hack rate == 0.25 (1 of 4)", m["reward_hack_rate"] == 0.25, m["reward_hack_rate"])
check("agg: verifier-select certifies the true one (coverage == pass@k)",
      m["bofn"]["verifier_select"]["certified_rate"] == m["pass_at_k"])
g2 = [ml.classify(rx, "(ab)*", P=["", "ab"], N=["a", "b"]) for rx in ["|ab|abab", "a*"]]
m2 = ml.aggregate([g2])
check("agg2: no correct => verifier ABSTAINS (never certifies wrong)",
      m2["bofn"]["verifier_select"]["abstain_rate"] == 1.0 and
      m2["bofn"]["verifier_select"]["certified_wrong_rate"] == 0.0)
check("agg2: judge-select certifies the hack (wrong-but-passing)",
      m2["bofn"]["judge_select"]["certified_wrong_rate"] == 1.0)

# 7. data: shapes + train/test language-leak check (must stay clean)
tr = ml.build_rows(ml.TARGETS_TRAIN, ml.TRAIN_BUDGETS)
te = ml.build_rows(ml.TARGETS_TEST, ml.TEST_BUDGETS)
check("rows: train prompts > 0", len(tr) > 0, len(tr))
check("rows: 24 held-out test tasks", len(te) == 24, len(te))
leak = [(a, b) for a in ml.TARGETS_TRAIN for b in ml.TARGETS_TEST if ml._equivalent(a, b)]
check("rows: NO train/test language leak", not leak, leak)

# 8. every LADDER arm constructs a working reward (except base, which skips training)
for tag, kind, L, seed in ml.LADDER:
    if kind == "base": continue
    fn = ml.make_reward(kind, L)
    out = fn(["a*", "((("], target=["a*"] * 2, pos=[["", "a"]] * 2, neg=[["b"]] * 2)
    check(f"arm {tag}: reward callable, len ok, invalid->0", len(out) == 2 and out[1] == 0.0, out)

print()
print("ALL GREEN" if not fails else f"{len(fails)} FAILURES: {fails}")
sys.exit(1 if fails else 0)
