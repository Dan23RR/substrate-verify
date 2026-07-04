"""
Drop-in reward functions for a real GRPO run (trl-compatible), for the L2 step:
train a small LLM with the deterministic verifier as the reward vs an LLM/example judge.

This file is importable without trl/torch/GPU (the reward functions are pure-Python and
run on CPU). The GRPO trainer block at the bottom is guarded: it only runs where trl +
a GPU are available. On such a box:

    dataset columns: {"prompt": <task prompt>, "target": <hidden target regex>,
                      "pos": [visible positives], "neg": [visible negatives]}

    from trl import GRPOConfig, GRPOTrainer
    trainer = GRPOTrainer(
        model="Qwen/Qwen2.5-0.5B-Instruct",
        reward_funcs=[verifier_reward_fn],        # <- arm A (sound)
        # reward_funcs=[example_judge_reward_fn], # <- arm B (baseline, hackable)
        args=GRPOConfig(...),
        train_dataset=ds,
    )
    trainer.train()

Prediction (from experiment.py results): arm B learns to memorize/overfit (reward hacking);
arm A learns to generalize.
"""
from greenery import parse

def _extract_regex(completion) -> str:
    """Get the model's proposed regex out of a completion (chat or text)."""
    if isinstance(completion, list):                       # chat format [{'role','content'}]
        completion = completion[-1].get("content", "")
    text = str(completion).strip()
    # take the last non-empty line, strip common code fences / backticks
    for line in reversed(text.splitlines()):
        line = line.strip().strip("`").strip()
        if line:
            return line
    return text

def _equivalent(rx1: str, rx2: str) -> bool:
    try:
        return parse(rx1).equivalent(parse(rx2))
    except Exception:
        return False

def _accepts(rx: str, s: str) -> bool:
    try:
        return parse(rx).to_fsm().accepts(s)
    except Exception:
        return False

def verifier_reward_fn(completions, target=None, **kwargs):
    """ARM A: sound reward. 1.0 iff the completion's regex is provably equivalent to target.
    trl passes dataset columns as kwargs lists; `target` is a list aligned with completions."""
    targets = target if isinstance(target, list) else [target] * len(completions)
    out = []
    for comp, tgt in zip(completions, targets):
        rx = _extract_regex(comp)
        out.append(1.0 if (tgt and _equivalent(rx, tgt)) else 0.0)
    return out

def example_judge_reward_fn(completions, pos=None, neg=None, **kwargs):
    """ARM B: example/surface judge (a faithful model of an LLM-as-judge shown the visible
    cases). 1.0 iff the regex agrees with all shown positives/negatives. HACKABLE."""
    n = len(completions)
    poss = pos if isinstance(pos, list) else [pos or []] * n
    negs = neg if isinstance(neg, list) else [neg or []] * n
    out = []
    for comp, P, N in zip(completions, poss, negs):
        rx = _extract_regex(comp)
        ok = all(_accepts(rx, p) for p in (P or [])) and all(not _accepts(rx, x) for x in (N or []))
        out.append(1.0 if ok else 0.0)
    return out

if __name__ == "__main__":
    # CPU smoke test of the reward functions (no GPU/trl needed).
    target = "(ab)*"
    comps = ["(ab)*", "```\n(ab)*(ab)*\n```", "|ab|abab", "a*b*"]  # correct, correct, HACK, wrong
    pos, neg = ["", "ab", "abab"], ["a", "b", "ba"]
    v = verifier_reward_fn(comps, target=[target]*len(comps))
    j = example_judge_reward_fn(comps, pos=[pos]*len(comps), neg=[neg]*len(comps))
    print("completions :", ["correct", "correct", "HACK", "wrong"])
    print("verifier    :", v)   # expect [1,1,0,0]  -> hack rejected
    print("example-judge:", j)  # expect [1,1,1,0]  -> hack REWARDED (fooled)
    assert v == [1.0, 1.0, 0.0, 0.0], v
    assert j == [1.0, 1.0, 1.0, 0.0], j
    print("\nOK: verifier rejects the hack, the example-judge rewards it. Drop into GRPOTrainer on a GPU box.")
