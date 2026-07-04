# Real GRPO run — verifier-as-reward vs LLM/example-judge-reward

The **L2 step**: train a small LLM on the regex-synthesis task with two different reward signals,
on a GPU, and measure which one *generalizes* and which one *reward-hacks*. Prediction (from the
CPU experiment in `../`, which already validated the reward signal): the **verifier arm generalizes,
the judge arm reward-hacks.**

Two ways to run it: **Modal** (recommended — reproducible, headless) or **Colab** (free T4).

## Option A — Modal (primary)
One-time:
```bash
pip install modal
modal token new
modal secret create huggingface HF_TOKEN=hf_xxx      # your Hugging Face token
```
Run + fetch:
```bash
modal run experiments/verifier_as_reward/gpu/modal_grpo.py            # optional: --max-steps 300 --k-eval 8
modal volume get grpo-verifier-results results.json ./results.json
```
GPU A10G, ~30-60 min for both arms, ≈ **$0.5-1.1** total.

## Option B — Colab (free T4)
New Colab > Runtime > T4 GPU. Paste each `# %% CELL` block of `colab_grpo.py` into its own cell.
Run cells 1-3 once; run 4-5 with `ARM="verifier"`, then re-run 2,4,5 with `ARM="judge"`. Compare
the two printed metric lines.

## Reading `results.json`
```
arm_verifier / arm_judge:
  verified_correct_rate  = outputs provably equivalent to the HELD-OUT target (true generalization)
  reward_hack_rate       = outputs that fit the shown examples but are NOT equivalent (the hack)
  parse_fail_rate        = outputs that don't parse as a regex
```
**The signal is the DIFFERENTIAL:** expect `arm_verifier` to have *higher* `verified_correct_rate`
and *lower* `reward_hack_rate` than `arm_judge`. Absolute numbers depend on model size and steps.

## Honest notes / falsifiability
- 0.5B is small. If **both** arms are near-zero verified_correct, bump `--max-steps` (300-500) or
  swap to `Qwen2.5-1.5B-Instruct` (still fits A10G, or T4 in 4-bit). Look for the *differential*, not perfection.
- If the verifier arm does **not** beat the judge arm, that is a real, **publishable NULL** — report it.
  The hypothesis is falsifiable by design; do not tune until it "wins".
- Troubleshooting: pin `trl==0.19.*` if a `GRPOConfig` arg errors; keep `num_generations` dividing
  `batch*grad_accum*world`; lower `gpu_memory_utilization` / `max_completion_length` on OOM.

## Files
- `modal_grpo.py` — self-contained Modal app (both arms + held-out eval), plain TRL + peft.
- `colab_grpo.py` — Colab cells, Unsloth 4-bit + LoRA.
- `tasks.py` — dataset + eval module (CPU-tested; the GPU files inline their own copy to stay standalone).
- `../grpo_reward.py` — the trl-compatible reward functions (CPU smoke-tested).
- `../RESULTS.md` — the CPU reward-signal experiment that motivates this run.
