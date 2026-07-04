"""
verifier-as-reward: does a deterministic verifier beat an LLM/example judge AS A REWARD SIGNAL?

Hypothesis (falsifiable): on a checkable task, a reward = deterministic verifier
(sound equivalence check) cannot be reward-hacked, whereas a reward = example/surface
judge (a faithful model of how an LLM-as-judge scores) can be, so optimizing the judge
reward leaves reward-hack mass in the policy while optimizing the verifier drives it to 0.

Environment note (honest): no GPU / no trl / no unsloth here, so we do NOT run gradient
GRPO on a real LLM. We test the LOAD-BEARING core on CPU with a SOUND oracle:
  (1) reward soundness (verifier 0 FP/0 FN by construction, measured);
  (2) reward-hacking: the example/LLM-style judge is fooled by memorization hacks;
  (3) a reward-weighted policy update (a faithful analog of what policy-gradient/GRPO
      does: increase the probability of high-reward candidates) run to convergence,
      measuring how much reward-hack mass survives under each reward.

Verifier oracle: greenery FSM regex equivalence (decidable, exact). The substrate-verify
kernel does the same via SMT; the reward function here is drop-in for a real GRPO loop.
"""
import json, itertools, math, os
from greenery import parse

ALPHABET = ["a", "b"]
ETA = 1.0          # reward-weighting temperature for the policy update
ITERS = 60         # policy-update steps
POS_CAP = 12       # cap on visible positive examples (memorization-hack size)
NEG_CAP = 12

# All targets are INFINITE languages (contain * or +), so no finite set of visible
# examples determines them -> a memorization hack is always inequivalent to the target.
TARGETS = [
    "a*",
    "a+",
    "(ab)*",
    "a*b*",
    "a(a|b)*",
    "(a|b)*a",
    "b*ab*",            # exactly one 'a'
    "(aa)*",            # even number of a's, no b
    "(a|b)*aa(a|b)*",   # contains 'aa'
    "(ab|ba)*",
]
BUDGETS = [2, 3, 4]     # max visible string length (the "how many examples" knob)

_fsm_cache = {}
def fsm(rx):
    if rx not in _fsm_cache:
        _fsm_cache[rx] = parse(rx).to_fsm()
    return _fsm_cache[rx]

def accepts(rx, s):
    return fsm(rx).accepts(s)

def equivalent(rx1, rx2):
    return parse(rx1).equivalent(parse(rx2))

def strings_upto(L):
    out = [""]
    for n in range(1, L + 1):
        out += ["".join(t) for t in itertools.product(ALPHABET, repeat=n)]
    return out

def make_task(target, L):
    """Return (P, N) visible pos/neg example sets, or None if degenerate."""
    P, N = [], []
    for s in strings_upto(L):
        (P if accepts(target, s) else N).append(s)
    if not P:            # nothing to memorize -> skip honestly
        return None
    return P[:POS_CAP], N[:NEG_CAP]

def memorization_hack(P):
    # alternation of the exact visible positives (literal strings). Empty string -> empty branch.
    return "|".join(P)

def judge_reward(cand, P, N):
    """Example/surface judge = 1 iff candidate agrees with the visible cases.
    This is the mechanism by which an LLM-as-judge (shown only the visible behavior)
    is fooled: it scores surface agreement, not the language."""
    try:
        return 1.0 if (all(accepts(cand, p) for p in P) and all(not accepts(cand, n) for n in N)) else 0.0
    except Exception:
        return 0.0

def verifier_reward(cand, target):
    """Sound reward = the verifier. 1 iff candidate is provably equivalent to the target."""
    try:
        return 1.0 if equivalent(cand, target) else 0.0
    except Exception:
        return 0.0

def policy_optimize(cands, rewards):
    """Reward-weighted multiplicative update (softmax over cumulative reward): a faithful
    analog of policy gradient / GRPO's effect -- push probability toward high-reward samples.
    Returns final policy (list of probs aligned with cands)."""
    w = [1.0] * len(cands)
    for _ in range(ITERS):
        w = [wi * math.exp(ETA * ri) for wi, ri in zip(w, rewards)]
        z = sum(w) or 1.0
        w = [wi / z for wi in w]
    return w

def run():
    tasks, skipped = [], 0
    for target in TARGETS:
        for L in BUDGETS:
            t = make_task(target, L)
            if t is None:
                skipped += 1
                continue
            P, N = t
            # --- candidate pool ---
            correct = [target, f"({target})"]                 # equivalent forms (verified below)
            wrong_src = TARGETS[(TARGETS.index(target) + 1) % len(TARGETS)]
            wrong = [wrong_src]
            hack = memorization_hack(P)
            pool = []
            for c in correct:
                pool.append((c, "correct"))
            for c in wrong:
                pool.append((c, "wrong"))
            pool.append((hack, "hack"))
            tasks.append(dict(target=target, L=L, P=P, N=N, pool=pool))

    # --- per-candidate rewards + ground truth ---
    conf_judge = dict(fp=0, fn=0, tp=0, tn=0)      # vs ground-truth equivalence
    conf_verif = dict(fp=0, fn=0, tp=0, tn=0)
    hack_fooled_judge = 0; hack_caught_verif = 0; n_hack = 0
    # equivalence sanity: are the labelled 'correct' actually equiv, 'hack'/'wrong' actually not?
    label_bad = 0

    per_budget_hack = {L: dict(judge_fp=0, verif_fp=0, n=0) for L in BUDGETS}

    for task in tasks:
        target, P, N = task["target"], task["P"], task["N"]
        for cand, label in task["pool"]:
            gt = 1.0 if verifier_reward(cand, target) == 1.0 else 0.0   # ground truth = equivalence (sound)
            rj = judge_reward(cand, P, N)
            rv = verifier_reward(cand, target)
            # ground-truth label sanity check
            if label == "correct" and gt != 1.0: label_bad += 1
            if label in ("hack", "wrong") and gt != 0.0: label_bad += 1
            # confusion vs ground truth
            for conf, r in ((conf_judge, rj), (conf_verif, rv)):
                if r == 1 and gt == 1: conf["tp"] += 1
                elif r == 1 and gt == 0: conf["fp"] += 1
                elif r == 0 and gt == 1: conf["fn"] += 1
                else: conf["tn"] += 1
            if label == "hack":
                n_hack += 1
                if rj == 1: hack_fooled_judge += 1
                if rv == 0: hack_caught_verif += 1
                per_budget_hack[task["L"]]["n"] += 1
                if rj == 1: per_budget_hack[task["L"]]["judge_fp"] += 1
                if rv == 1: per_budget_hack[task["L"]]["verif_fp"] += 1

    # --- optimization / policy simulation (RL analog) ---
    def sim(reward_fn):
        vc_masses, hack_masses = [], []
        for task in tasks:
            target, P, N = task["target"], task["P"], task["N"]
            cands = [c for c, _ in task["pool"]]
            labels = [l for _, l in task["pool"]]
            rewards = [reward_fn(c, target, P, N) for c in cands]
            pol = policy_optimize(cands, rewards)
            # truly-correct mass and hack mass under the converged policy
            vc = sum(p for p, c in zip(pol, cands) if verifier_reward(c, target) == 1.0)
            hk = sum(p for p, l in zip(pol, labels) if l == "hack")
            vc_masses.append(vc); hack_masses.append(hk)
        return sum(vc_masses)/len(vc_masses), sum(hack_masses)/len(hack_masses)

    vc_verif, hk_verif = sim(lambda c, t, P, N: verifier_reward(c, t))
    vc_judge, hk_judge = sim(lambda c, t, P, N: judge_reward(c, P, N))

    def rate(conf):
        tot = sum(conf.values())
        return dict(conf, fp_rate=round(conf["fp"]/tot, 4), fn_rate=round(conf["fn"]/tot, 4), n=tot)

    results = dict(
        setup=dict(alphabet=ALPHABET, n_targets=len(TARGETS), budgets=BUDGETS,
                   n_tasks=len(tasks), skipped=skipped, iters=ITERS, eta=ETA,
                   verifier_oracle="greenery FSM regex equivalence (sound); kernel does same via SMT"),
        label_sanity_violations=label_bad,
        reward_soundness=dict(verifier=rate(conf_verif), judge=rate(conf_judge)),
        reward_hacking=dict(
            n_hack_candidates=n_hack,
            judge_fooled_by_hack=hack_fooled_judge,
            judge_fooled_rate=round(hack_fooled_judge/n_hack, 4) if n_hack else None,
            verifier_caught_hack=hack_caught_verif,
            verifier_caught_rate=round(hack_caught_verif/n_hack, 4) if n_hack else None,
        ),
        hack_by_example_budget={str(L): dict(n=per_budget_hack[L]["n"],
                                             judge_fp_rate=round(per_budget_hack[L]["judge_fp"]/per_budget_hack[L]["n"],4) if per_budget_hack[L]["n"] else None,
                                             verifier_fp_rate=round(per_budget_hack[L]["verif_fp"]/per_budget_hack[L]["n"],4) if per_budget_hack[L]["n"] else None)
                               for L in BUDGETS},
        policy_optimization=dict(
            verifier_reward=dict(mean_verified_correct_mass=round(vc_verif,4), mean_hack_mass=round(hk_verif,4)),
            judge_reward=dict(mean_verified_correct_mass=round(vc_judge,4), mean_hack_mass=round(hk_judge,4)),
        ),
    )
    return results

if __name__ == "__main__":
    res = run()
    out = os.path.join(os.path.dirname(__file__), "results.json")
    with open(out, "w") as f:
        json.dump(res, f, indent=2)
    print(json.dumps(res, indent=2))
    print("\nwrote", out)
