# verifier-as-reward

A controlled, falsifiable experiment: **is a deterministic verifier a better reward signal than an LLM/example judge?**

This is the first concrete step of turning `substrate-verify` from an output *checker* into a *training signal* (RLVR/GRPO) — the "go deeper" move.

## Headline result (measured, CPU, `results.json`)

| | Verifier reward | LLM/example judge reward |
|---|---|---|
| False-positive rate | **0%** | 25% |
| Fooled by memorization hack | **0 / 30** | **30 / 30 (100%)** |
| Reward-hack mass left after optimization | **0%** | **33%** |
| Hack-FP as visible examples grow (L=2/3/4) | 0/0/0% | 100/100/100% |

The verifier is a sound reward and cannot be reward-hacked; the surface/LLM-style judge is fooled by 100% of memorization hacks, and *no amount of visible examples fixes it*. Optimizing the unsound reward steers the policy into the hack (33% mass); optimizing the verifier drives it to zero. **Hypothesis held.**

## Files
- `experiment.py` — the experiment (30 tasks: regex synthesis over `{a,b}`, sound greenery equivalence oracle). Run: `python experiment.py`.
- `results.json` — measured output.
- `RESULTS.md` — full writeup + **honest scope** (this is a reward-signal / optimization experiment on CPU, *not* a gradient GRPO run on a real LLM; the judge is a principled model of the surface-judging failure mode).
- `grpo_reward.py` — the verifier exposed as a **`trl`-compatible reward function**, ready to drop into `GRPOTrainer` on a GPU box for the full L2 run. Smoke test: `python grpo_reward.py`.

## Deps
`pip install greenery` (experiment). For the full run: `trl`, `unsloth`, a GPU.
