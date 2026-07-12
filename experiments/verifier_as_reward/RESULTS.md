# verifier-as-reward — results

**Question.** Is a deterministic verifier a *better reward signal* than an LLM/example judge? Specifically: can it be reward-hacked, and does optimizing it leave hack mass in the policy?

**Hypothesis (falsifiable).** On a checkable task, reward = deterministic verifier (sound equivalence) is immune to a memorization reward-hack that fools an example/surface judge, and optimizing the verifier reward drives reward-hack mass to zero while optimizing the judge reward does not.

## What was run

- **Task.** Regex synthesis over the alphabet `{a,b}`: given visible example strings, produce a regex equivalent to a hidden target. 10 infinite-language targets x 3 visible-example budgets (max length 2/3/4) = **30 tasks**, 0 skipped.
- **Verifier reward** = 1 iff the candidate is provably equivalent to the target. Oracle: **greenery FSM equivalence** (decidable, exact). The substrate-verify kernel does the same via SMT; the reward function is drop-in for a real GRPO loop.
- **Judge reward** (a faithful model of an LLM-as-judge shown only the visible behavior) = 1 iff the candidate agrees with the target on all visible examples. It scores *surface agreement on the shown cases*, which is exactly how an example-conditioned LLM-judge is fooled.
- **Reward-hack candidate** = the memorization regex `"|".join(visible_positives)` — matches the shown positives exactly, so it maxes the judge, but (target is infinite) is never equivalent to the target. **All 30 hacks were confirmed genuinely inequivalent by greenery (label-sanity violations = 0).**
- **Policy-optimization analog.** A reward-weighted multiplicative update (softmax over cumulative reward, eta=1, 60 steps) — a faithful analog of what policy gradient / GRPO does: push probability toward high-reward candidates. Measured how much *verified-correct* mass and *reward-hack* mass survive at convergence, per reward.

## Results (measured, `results.json`)

| Metric | Verifier reward | Judge reward |
|---|---|---|
| False-positive rate (vs ground-truth equivalence, n=120) | **0.00** | **0.25** |
| False-negative rate | 0.00 | 0.00 |
| Fooled by memorization hack (n=30) | **0 / 30 (0%)** | **30 / 30 (100%)** |
| Hack FP rate at example budget L=2 / 3 / 4 | 0% / 0% / 0% | 100% / 100% / 100% |
| **Policy at convergence: verified-correct mass** | **1.000** | **0.667** |
| **Policy at convergence: reward-hack mass** | **0.000** | **0.333** |

## What it shows

1. **Soundness.** The verifier reward has 0 false positives / 0 false negatives by construction, confirmed on all 120 candidate scorings. The judge reward has a 25% false-positive rate — every one of those false positives is a reward-hack it cannot see through.
2. **Reward hacking is real and one-sided.** The example/LLM-style judge is fooled by **100%** of memorization hacks; the verifier catches **100%**.
3. **More examples do not save the judge.** Sweeping the visible-example budget (L=2->4) leaves the judge's hack-FP rate pinned at 100% while the verifier stays at 0%. This is the deep point: *no finite set of shown examples makes a surface judge sound* — the hack just memorizes more. The verifier checks the language, not the shown cases, so it is immune.
4. **Optimizing the reward inherits its unsoundness.** Under the verifier reward the policy converges to 100% verified-correct, 0% hack. Under the judge reward it converges to 33% reward-hack mass (with this pool: 1 hack among 3 reward-1 candidates). The unsound reward does not just mis-score once — *it steers the optimizer into the hack.*

## Honest scope (what this is, and is not)

- This is a **controlled experiment on the reward signal and its optimization**, on CPU. It is **not** a gradient-based GRPO run on a real LLM: this machine has no GPU and no `trl`/`unsloth`. The claim demonstrated is the load-bearing one (reward soundness -> hack-immunity -> hack-free optimization); the full LLM training run is the drop-in next step (`grpo_reward.py`).
- The judge is a **principled model of the surface-judging failure mode**, not a real LLM. A real LLM-judge may do better or worse on any given case; the point proved is the **mechanism**: any judge that scores finite visible behavior is foolable by memorization, and a language-level verifier is not. We do not claim "LLMs are 25% wrong" — we claim example/surface judging is *unsound as a reward* and the verifier is *sound*.
- The hack is constructed to be example-consistent-but-inequivalent, so the numbers are near-deterministic. That is a feature: it is a clean mechanism demonstration / existence proof, reported with its construction, not a noisy empirical estimate.

## Falsification

The hypothesis would have failed if: the verifier had shown any FP/FN (it did not: 0/0), or the memorization hack had turned out equivalent to some target (label-sanity caught 0 such cases), or judge-optimization had driven hack mass to 0 (it did not: 0.333). None occurred. Result: **hypothesis held.**

## Reproduce

```bash
pip install greenery
python experiments/verifier_as_reward/experiment.py   # writes results.json, prints the table above
```

## Next step (concrete, drop-in)

`grpo_reward.py` exposes the verifier as a `trl`-compatible reward function. On a GPU box with `trl`+`unsloth`, plug it into `GRPOTrainer(reward_funcs=[verifier_reward_fn])` on a small model (Qwen-0.5B) and run the same two arms (verifier reward vs LLM-judge reward) end-to-end.

---

# L2 — real GRPO run (Qwen2.5-0.5B, Modal A10G, 2026-07-01)

Trained the two arms end-to-end (300 GRPO steps each) with **dense-but-sound rewards** (verifier: probe-agreement over strings up to length 6 + an exact-equivalence bonus, so only a truly equivalent regex reaches 1.0 and a memorization hack caps at ~0.5; judge: agreement on the visible examples, which a hack maxes). Held-out test targets (12 tasks, 96 sampled completions per arm). `gpu/results.json`.

| held-out metric | verifier-reward arm | judge-reward arm |
|---|---|---|
| verified_correct_rate (true generalization) | 0.00 | 0.00 |
| **reward_hack_rate** (fits shown examples but NOT equivalent) | **0.00** | **0.67 (64/96)** |
| parse_fail_rate | 0.00 | 0.00 |

**The load-bearing finding, shown end-to-end on a real trained model:** training against the LLM/example-judge reward **induces reward-hacking (67%)** — the model learns to emit outputs that fit the shown examples but are not equivalent. Training against the deterministic verifier reward **induces none (0%)**, because example-fitting-but-wrong earns no credit under it. This is exactly the danger the CPU experiment predicted, now confirmed on a trained policy.

**Honest limitation:** neither 0.5B model reached exact equivalence on held-out targets (both 0% verified_correct) — at this scale, generalizing to an unseen target's exact language is out of reach. So the verifier arm's value here is *not-hacking*, not *solving*: its outputs are wrong-but-non-deceptive (they don't even fit the shown examples), whereas the judge arm's are deceptive-passing. The complementary claim (the verifier arm also *generalizes better*) is **not** established at this scale and would need a larger model / denser curriculum to test. Reported as-is; not tuned until the verifier "wins".

**Bottom line:** the reward-hacking asymmetry (67% vs 0%) is decisive and is the point. A verifier is a reward you cannot game; an LLM/example judge is one the model learns to game.

Iteration honesty: this took three real fixes on the live GPU (a removed TRL kwarg `max_prompt_length`; an `apply_chat_template` BatchEncoding vs tensor in eval; and — the substantive one — the exact-equivalence reward being too sparse for a 0.5B to bootstrap, fixed with the dense-but-sound reward above). Each failure taught something; none was papered over.

---

# L2 — ambitious run (Qwen2.5-1.5B, Modal A10G, 2026-07-01): THE FULL RESULT

Scaled up: 1.5B model, 600 steps, num_generations=8, 3 example budgets (L=3,4,5) -> 57 train prompts, 24 held-out test tasks (leak-checked: no test target shares a language with any train target), k=16 samples/task, added a **pass@k** metric.

| held-out metric | **verifier-reward arm** | **judge-reward arm** |
|---|---|---|
| verified_correct_rate (exact equivalence) | **0.112** (43/384) | **0.000** |
| **pass@k** (task solved at least once in 16) | **0.125** (3/24 tasks) | **0.000** |
| **reward_hack_rate** | **0.000** | **0.625** (240/384) |
| parse_fail_rate | 0.010 | 0.000 |

**The hypothesis is now confirmed in BOTH directions on a trained model:**
1. **Generalization:** the verifier-reward model produces exactly-equivalent regexes on *unseen* targets 11.2% of the time and solves 3/24 held-out tasks; the judge-reward model does so **never** (0%).
2. **No reward-hacking:** the verifier-reward model produces **zero** deceptive (example-fitting-but-wrong) outputs; the judge-reward model produces them **62.5%** of the time.

So: **training against the deterministic verifier produced a model that is both more correct and non-deceptive; training against the LLM/example judge produced a model that is never correct and mostly deceptive.** The reward you cannot game yields a model that actually learns the task; the reward the model can game yields a model that only learns to game it.

**Honest calibration:** 11.2% / pass@k 12.5% is modest in absolute terms — exact regex equivalence on held-out targets from a 1.5B is a hard bar, and there is lots of headroom (bigger model, more steps, curriculum). The *comparison*, however, is decisive and one-sided: verifier >> judge on generalization (0.112 vs 0.000) and verifier << judge on hacking (0.000 vs 0.625). This was falsifiable — it could have come out null (both zero) — and it did not.

**One-line takeaway for the write-up / for Cordeiro:** *an LLM post-trained against a deterministic verifier as reward generalizes to unseen tasks and does not reward-hack; the same model trained against an LLM-as-judge reward learns to hack the judge (62.5%) and never generalizes.*

---

# L2 — scale sweep (0.5B -> 1.5B -> 3B): the finding sharpens

Ran the same two arms at three model scales (held-out targets, leak-checked). Verifier reward vs example/LLM-judge reward.

| model | verifier: generalizes (pass@k) | verifier: hacks | judge: generalizes | **judge: hacks** |
|---|---|---|---|---|
| Qwen2.5-0.5B (300 steps) | 0% | 0% | 0% | 67% |
| Qwen2.5-1.5B (600 steps) | 12.5% (3/24) | 0% | 0% | 62.5% |
| Qwen2.5-3B (900 steps) | 12.5% (3/24) | 0% | 0% | **95.5%** |

**Two findings, both honest:**

1. **Reward-hacking gets WORSE with scale under the unsound reward, and the verifier stays immune at every scale.** Trained against the LLM/example judge, the model games it 67% -> 62.5% -> **95.5%** as it grows (the 3B produces 550/576 deceptive outputs). Trained against the verifier, reward-hacking is **0% at every scale**. This is the safety-relevant result: a more capable model exploits an unsound reward *harder*; only a reward it cannot game (the verifier) stays safe. The danger the verifier removes **grows with capability**, which is exactly why it matters for stronger AI.

2. **Generalization plateaued (honest limitation).** The verifier arm jumped 0% -> 12.5% from 0.5B to 1.5B, then **did not improve at 3B** (both solve ~3/24 held-out tasks). So on this task, model scale is *not* the lever for higher generalization; the bottleneck is task difficulty / reward shaping / data, not capacity. We report the plateau rather than hiding it or chasing a bigger model until it moves.

**Sharpened takeaway:** *the reward-hacking problem is not fixed by scale — it grows with it (up to 95.5%), and only a deterministic verifier reward is immune (0% at every scale). That is the case for verifier-as-reward as a load-bearing primitive for more capable AI.*

> ⚠️ **CAVEAT (added 2026-07-02, after the pre-registered E1 ladder run — see `gpu/RESULTS_ladder.md`):** the sweep above is **one seed per scale**. A 3-seed replication at 1.5B found judge hacking spans **49.7–96.4%** across seeds, and the verifier arm's 0% held at only **1 of 3 seeds** (the dense probe-agreement shaping term is itself exploitable: at 2/3 seeds the policy settled on plausible-but-wrong outputs, which the verifier never certifies but still emits). Consequences: (1) "grows with scale" is downgraded to a single-seed observation pending a multi-seed sweep (E2); (2) the robust, seed-independent claims are: deception is reward-induced (both controls at 0% hack), the sound verifier as selector never certifies a wrong output (0/264 arm-tasks, vs 54–100% wrong certifications for the judge selector), and only the verifier arm ever generalizes (at every seed). **Do not quote the sweep table without this caveat.**

---

# L3 — E1 soundness ladder + controls (Qwen2.5-1.5B, 11 arms, Modal A10G, 2026-07-02)

Pre-registered (6 predictions in `gpu/PREREG_ladder.md`, written before launch), 3 seeds on the two extreme arms, a bounded-soundness ladder (L=2/4/6) in between, and two control arms (syntax-only reward; untrained base). Full scoring in **`gpu/RESULTS_ladder.md`**; per-arm JSONs in `gpu/ladder_results/`; LoRA adapters saved on the Modal volume for reuse.

Outcome in one line: **P2 confirmed** (controls at 0% hack → the deception is reward-induced; the hack metric survives its designed killer), **P5 confirmed** (sound selector: 0 wrong certifications across all 11 arms; judge selector: 54–100%; and filtering the judge-trained model with the verifier does NOT recover the verifier-trained arm's correctness → training is not replaceable by filtering at this scale), **P6 falsified** (judge hack seed-spread ~47pp; verifier 0% at only 1/3 seeds), **P1/P4 partial** (ladder monotone in means, flat between bounded rungs; bounded arms exploit their own unverified region at L=2,4 but not L=6), **P3 falsified as designed** (error migration must be measured on train targets, not held-out; adapters saved for that follow-up).

New finding (from the falsification): **the weakest-link rule applies to composite rewards.** The dense-but-sound reward = 0.5·probe-agreement (empirical tier) + 0.5·exact equivalence (proven tier); at 2/3 seeds the optimizer maximized the empirical half and ignored the sparse proven half — the near-miss basin even pays a *higher* mean training reward (0.68) than the honest basin (0.44). *[Update 2026-07-10: with the E2 seeds in hand this reward-ordering is itself seed-anecdotal — an honest E2 seed at the same scale ends at 0.67. The basin structure stands; the "near-miss pays more" ordering is withdrawn.]* The policy's behavior inherits the assurance tier of the component the optimizer actually maximizes, not of the strongest component present — the certificate-composition rule (system verdict = weakest link), observed on the training side.

The two overclaims this run caught ("0% at every scale", "grows with scale") were corrected in the public writeup §8 and in the Cordeiro follow-up draft **before** either went out.

---

# L4 — E2 multi-seed scale sweep (0.5B/1.5B/3B × 5 seeds, 600 steps fixed, 2026-07-02)

Pre-registered in `gpu/PREREG_e2.md`; full scoring in **`gpu/RESULTS_e2.md`**; 27 runs + 6 reused from E1, 0 failures, ~$20-25. **Resolves the E1 caveat above:** with 5 seeds per scale and optimization compute FIXED at 600 steps, the growth of judge-reward hacking with scale is **re-established with error bars**: 62.3±0.2% (0.5B) → 66.7±17.5% (1.5B) → **93.3±5.1% (3B)**, Δ=31pp vs 2·SE=4.6pp, monotone (P1 confirmed). Second headline (P4): the verifier arm's **honest basin becomes the universal attractor with scale — 1/5 → 2/5 → 5/5 seeds honest**; scale is a *bidirectional* amplifier (worsens gaming of the unsound reward, consolidates honesty under the sound one; E1's bimodality was the transition regime at 1.5B). Certification stayed perfect: **0 wrong certifications in 792 task-level selections across all 33 runs** (P3), judge-selector up to 100% wrong. Unregistered honest findings: (a) the unsound reward **unteaches** — 3B base solves 16.7% of held-out tasks via verifier-filtered sampling, judge-training drives that to 0% at all 5 seeds while producing 93% deception; (b) at 3B, verifier-training's value over filtering the base is per-sample reliability (14.1% vs 4.2% per-completion, ~3.4×), not coverage (~equal pass@k) — at 1.5B training was necessary for coverage too. Remaining gates: one domain only (E4 for "law" status), no extrapolation beyond 3B (E2b optional).

---

# L5 — E4 trans-domain: firewall rule-sets (30 runs, 2026-07-03)

Second domain, built to be structurally different (finite 64-packet space, first-match semantics, never-seen DSL; exhaustive check ⇒ the verifier reward has NO partial-coverage component). Pre-registered in `gpu/PREREG_e4.md`; full scoring in **`gpu/RESULTS_e4.md`**; ~$30, 0 failures. **P1 CONFIRMED at 16 SE:** judge hacking grows with scale here too — **5.1% → 100% → 91.8%** (saturating earlier than regex: curve *shape* is domain-dependent, *direction* transfers, 2/2 domains). **P3 perfect again:** 0 wrong certifications in all 30 runs, coverage==pass@k verified — cumulative across both domains: **0 gate errors in 1,512 task-level selections**; judge-selector certifies wrong outputs on 100% of tasks at 1.5B. **P6 FALSIFIED (the mechanistic result):** the near-miss attractor appears even under a fully sound reward (verifier-arm hack 37-62% at 1.5B, 10-24% at 3B) → the E1 weakest-link explanation is incomplete; **dense partial credit itself sustains the near-miss basin** whenever exact success is harder than the marginal gain (a weak component aggravates but is not required). The sound gate still never certifies those near-misses, and here they coexist with much stronger generalization (22.7% correct at 1.5B vs regex's 7.3%). **P2 confirmed:** the judge-trained model occasionally generalizes here (2/5 seeds at 3B, ≤9.4%; never on regex) — first brick of the soundness-gap taxonomy. **P4 falsified in this domain:** the honest basin is NOT universal at 3B here (1/5 vs regex's 5/5); direction 1.5→3B is right (hack halves) but the "remedy scales to 100%" part of the E2 story is domain-dependent — writeup §8 qualified accordingly. **P5 inconclusive** (pre-declared caveat applied: the base has little latent competence in the new DSL to destroy). Paired dominance holds at every seed/scale pair in this domain.
