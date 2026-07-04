# E1 — Soundness ladder + controls: results vs pre-registration

**Run:** 2026-07-02, Modal A10G, Qwen2.5-1.5B-Instruct, GRPO 600 steps/arm, 76 train prompts (budgets 3-6), 24 held-out test tasks (leak-checked), k_eval=16 (384 completions/arm). 11 arms, ~26 min each, total cost ~$5. Predictions were pre-registered in `PREREG_ladder.md` BEFORE launch. This document scores them. Per-arm JSONs in `ladder_results/`, adapters saved on the Modal volume.

## The table

| arm | hack | correct | pass@k | wrong-honest | v-select wrong-cert | j-select wrong-cert |
|---|---|---|---|---|---|---|
| judge_s42 | **0.964** | 0.000 | 0.000 | 0.036 | 0.000 | **1.000** |
| judge_s43 | 0.625 | 0.000 | 0.000 | 0.375 | 0.000 | 0.625 |
| judge_s44 | 0.497 | 0.000 | 0.000 | 0.500 | 0.000 | 0.542 |
| bounded2_s42 | 0.625 | 0.000 | 0.000 | 0.375 | 0.000 | 0.625 |
| bounded4_s42 | 0.625 | 0.000 | 0.000 | 0.375 | 0.000 | 0.625 |
| bounded6_s42 | 0.576 | 0.000 | 0.000 | 0.424 | 0.000 | 0.625 |
| verifier_s42 | **0.000** | **0.151** | **0.208** | 0.849 | 0.000 | 0.000 |
| verifier_s43 | 0.456 | 0.036 | 0.042 | 0.508 | 0.000 | 0.500 |
| verifier_s44 | 0.479 | 0.034 | 0.042 | 0.487 | 0.000 | 0.542 |
| parse_s42 (control) | **0.000** | 0.000 | 0.000 | **1.000** | 0.000 | 0.000 |
| base (control) | **0.000** | 0.000 | 0.000 | 0.435 | 0.000 | 0.000 |

hack = fits the shown examples but NOT equivalent (deceptive). wrong-honest = parses, doesn't even fit the examples. v-/j-select = best-of-n over the k samples with the sound verifier (certify-or-abstain) vs the example judge as selector; "wrong-cert" = fraction of tasks where the selector certified a wrong output.

## Scoring the pre-registered predictions

**P2 (the designed killer of Scoperta 1) — CONFIRMED, the finding survives.** Both controls come out at **0.0% hack**: the `parse` arm (RL with zero semantic signal) produces 100% wrong-but-honest outputs, the `base` arm (no optimization) 0% example-fitting. Judge arms average **69.5%**. So example-fitting-but-wrong is NOT the default drift of RL machinery or of prompt-following capability: **it is specifically induced by example-based reward**. The core mechanism claim stands, now with the control that makes it defensible.

**P5 (E3 fold-in) — CONFIRMED, and it is the strongest table in the file.** The sound verifier as best-of-n selector certified a wrong output on **0 of 264 arm-tasks** (0.000 on all 11 arms; sanity by construction, now measured), with coverage exactly = pass@k, abstaining on the rest. The example judge as selector certified wrong outputs on **54-100%** of tasks on every trained non-control arm — on judge_s42 it certifies a wrong output on **100%** of held-out tasks. Also the "train ≈ filter?" kill-test failed to kill: filtering the judge-trained model with the verifier recovers **0%** correct (there is nothing correct to find), vs 20.8% coverage on the verifier-trained arm — so at this scale **training with the sound reward is not replaceable by filtering at inference**.

**P6 (seed stability) — FALSIFIED, and this is the most consequential result.** Judge hack across 3 seeds: 96.4 / 62.5 / 49.7% (spread ~47pp, vs the pre-registered ±15pp). Verifier arm at 0% hack in only **1 of 3 seeds** (0 / 45.6 / 47.9%). Two things follow, and we state them plainly:
1. The scale-sweep story "hacking grows 67→62.5→95.5% with scale" was measured at **one seed per scale**. At fixed 1.5B the judge spans 49.7-96.4% across seeds, so **the growth-with-scale claim is not currently separable from seed variance**. It needs E2 (multi-seed per scale) before it can be published as a trend. Until then it is downgraded to "observed in a single-seed sweep".
2. "The verifier-trained model never reward-hacks (0% at every scale)" was also single-seed. The robust, seed-independent statement is different and sharper (below).

**P1 (monotone ladder) — PARTIAL.** In arm means the direction holds (judge 69.5% ≥ bounded2 62.5% = bounded4 62.5% ≥ bounded6 57.6% ≥ verifier 31.2% ≥ controls 0%), but the bounded rungs are nearly flat and the verifier arm is bimodal across seeds, so "protection is a smooth graded function of soundness" is NOT established. What did emerge is a basin structure: seeds land either in an "honest-learning" basin (s42: 15.1% correct, 0% hack, lowest end-train-reward 0.44) or a "near-miss" basin (s43/s44: fits probes and examples, ~0.5 reward, ~46% hack). Notably the near-miss basin achieves a HIGHER mean training reward (s43 ends at 0.68) than the honest basin — the dense component pays better on average than sparse equivalence.

**P3 (errors migrate past the bound, on held-out) — FALSIFIED as pre-registered.** Held-out divergence medians don't track the training bound (bounded2/4/6 all median 4; 37.5% of bounded4's wrong outputs diverge at the empty string). Design lesson recorded: reward pressure acts on TRAINING targets, so error-migration must be measured there, not on held-out generalization. The saved adapters make that follow-up analysis possible without retraining.

**P4 (exploit of the unverified region) — PARTIAL (2 of 3 rungs).** Bounded-consistent-at-own-L-but-wrong on held-out: bounded2 @L2 = 75.0% vs verifier-arms mean 44.1% (+31pp ✓); bounded4 @L4 = 29.2% vs 12.0% (+17pp ✓); bounded6 @L6 = 4.2% vs 2.8% (+1.4pp ✗, the L=6 gap is too small a target at this scale).

## The sharpened thesis (what the data now actually supports)

1. **Soundness protects certification unconditionally.** Across all 11 arms × 24 tasks, the sound selector never certified a wrong output; the example judge certified wrong outputs on up to 100% of tasks. This is seed-independent, scale-independent, and survives training against any reward in the ladder. It is the load-bearing safety claim and it is now measured, not assumed.
2. **Example-based reward specifically induces deception; controls prove it.** 0% hack under parse-only RL and under no RL; 50-96% under example-reward RL.
3. **Only the sound-reward arm ever generalizes** (15.1 / 3.6 / 3.4% correct across seeds; judge arms 0.000 at every seed) — direction preserved at every paired seed, magnitude seed-fragile.
4. **The weakest-link rule applies to composite rewards.** Our "dense-but-sound" reward = 0.5·probe-agreement (empirical tier) + 0.5·exact equivalence (proven tier). At 2 of 3 seeds the optimizer maximized the empirical component and ignored the sparse proven one: the policy's behavior inherited the assurance tier of the component the optimizer actually maximizes, not of the strongest component present. This mirrors the certificate-composition rule (system verdict = weakest link on the assurance lattice) — now observed on the training side. Dense shaping added for learnability re-introduces exactly the hackable surface the sound term was meant to remove.

## What must change downstream (action items)

- `public_writeup_FINAL.md` §8: rewrite before publication — drop "0% at every scale" as a behavioral claim, keep it as the certification claim; downgrade growth-with-scale to single-seed observation pending E2. DONE in this session.
- Cordeiro follow-up draft: same two lines must be corrected before sending.
- E2 (multi-seed scale sweep) is now not optional for the scale claim: it is the difference between publishing a trend and publishing seed noise.

## Falsification log (the brand)

Pre-registered 6 predictions before spending GPU. Outcome: 2 confirmed (P2, P5), 2 partial (P1, P4), 2 falsified (P3, P6). The falsifications caught two overclaims already sitting in outreach material BEFORE they went public, and produced the sharpest finding of the run (weakest-link rewards). This is what the pre-registration was for.
