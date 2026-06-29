# Executable certificates instead of LLM-as-judge: a verification kernel, a benchmark, and where it fails

*Daniel Culotta, independent researcher. Draft for LessWrong / AI Alignment Forum, mirrored as an arXiv note (cs.LO / cs.AI). Every number below comes from scripts on disk and two adversarial audit passes that re-ran them. The "Where it fails" section is not a disclaimer at the end. It is the point.*

---

## Summary

The standard way to check the output of a language model is to ask another language model whether it looks right. This is cheap and general, and it inherits the failure modes of the system it is checking. I describe a different primitive: a small trusted kernel that checks a claim by **executing** it against a specification, and returns one of three verdicts, each as a signed certificate anyone can rerun. A refutation is an executed counterexample and counts as a proof. A confirmation is execution-backed evidence tagged with the assurance it actually earned, and is explicitly not treated as a proof. An abstention is a typed reason for not deciding, never a silent pass. The kernel is built so that claiming more than the evidence justifies is impossible by construction.

On a labelled set of ERC-4626 smart-contract vaults, ten independent LLM auditors produced both false positives and false negatives. The deterministic checker classified the same set with neither. The approach works wherever an output has checkable structure, which is a smaller set than "all model output," and the honest open problem is how to get a usable specification cheaply for the outputs that do not come with one.

This post gives the design, the results, the places it breaks, and a repository you can run.

## 1. The problem, measured

LLM-as-judge is now the default evaluation primitive. A second probabilistic model grades the first. It is convenient, and it cannot give a guarantee, because it has the same blind spots as the thing it grades. It is confident when it should not be, it is moved by surface form, and it has no notion of a counterexample.

Here is what that costs, measured on real targets. I pointed ten independent LLM auditors at the same labelled set of ERC-4626 vaults. On one vault that is genuinely safe, all ten flagged it as vulnerable. On a vault with a real, version-specific bug, four of the ten missed it. The judges were wrong in both directions at once: a false alarm on the safe case that would block a correct deploy and waste audit time, and a miss on the dangerous case.

The claim of this post is deliberately narrow. **Wherever an output has checkable structure, you do not need a smarter judge. You need an adjudicator that executes the claim and cannot overclaim.**

## 2. The design

The kernel is small, about 300 lines, with no dependency beyond a solver. It sits between an untrusted *prover* and a verdict. The prover is anything: a language model, a heuristic, a search procedure. It submits a *falsifiable claim* about a target. "These two regular expressions accept the same language." "This vault cannot be drained by a donation." "These two firewall rule sets accept exactly the same packets." The kernel adjudicates by executing the claim and returns one of three things.

- **REFUTED.** An executed counterexample. A distinguishing string, a draining transaction, a packet that one rule set accepts and the other drops. This is sound regardless of how the claim was produced. A counterexample is a fact about the world, not an opinion about the prover.
- **CONFIRMED.** Execution-backed evidence, tagged with the assurance tier it actually earned. An exhaustive check over a declared bound is not a universal proof, and the certificate records which one it is.
- **ABSTAIN.** A typed reason for not deciding. Never a silent pass.

Every verdict is serialized as an **Ed25519-signed, content-hashed certificate** that reruns offline. Sign with the wrong key and the certificate is rejected. The certificates **compose**: a system-level verdict is the weakest link of its parts, and the composition rule is explicit, so two components that are each individually safe but jointly exploitable under a shared dependency are caught, and the safe certificate is withheld rather than emitted.

## 3. The asymmetry that does the work

Everything hangs on one decision. **A refutation is a proof. A confirmation is not.** A counterexample stands on its own. A "looks fine" never does. It is only as strong as the oracle that produced it and the coverage that oracle had.

The kernel enforces this with an assurance lattice, ordered `none < empirical < bounded < proven`. A verdict cannot be labelled stronger than the evidence that earned it. Overclaim is not discouraged by convention, it is impossible to express. That is the property that lets you trust a checking stack even when the prover searching it is adversarial, which is exactly the regime that matters as models get better at finding things, including weaknesses in your checker.

## 4. Does it work? The honest table

| Claim | Evidence | Assurance tier it earns |
|---|---|---|
| Regex equivalence, real corpus | 1000 real GitHub patterns, 111 signed equivalence collapses, 72 hidden multi-syntax equivalences surfaced | proven (SMT) |
| Bounded constitution check | 780 of 780 admitted, malicious case rejected, the 780 reproduced from first principles | bounded-exhaustive, **not universal** |
| Firewall rule-set equivalence | 8 of 8, a refutation is a concrete packet rerun against a first-match interpreter | proven (SMT, QF_BV) |
| ERC-4626 exec-gate (VeriVault) | 0 false positives and 0 false negatives on 7 labelled real vaults, including a historically vulnerable OpenZeppelin 4.8 build; 22 live mainnet vaults classified as 16 immune, 0 vulnerable, 6 abstain | empirical, executed witness |
| Anti-cosmetic signatures | wrong key, certificate invalid | proven (cryptographic) |
| Versus LLM-as-judge | 10 of 10 false positive and 40% miss for the judges, 0 and 0 for the exec-gate | measured |

The exec-gate deserves a sentence of its own, because it runs the actual exploit rather than reasoning about it. It reproduces the real Compound v2 empty-market incident class, the family behind the Sonne, Hundred, and Onyx losses, by executing the draining transaction and producing the stolen amount as a witness. You can rerun the certificate and watch the balance move.

The backbone here is deterministic and was re-checked by two adversarial audit passes (2026-06-05 and 2026-06-06) that re-ran every script and recomputed the certificates by hand. They found only circumscribed, cosmetic overclaims, listed and fixed, and no soundness hole.

## 5. Where it fails

This is the section that makes the rest trustworthy, so it is not at the bottom by accident, and I am not going to soften it.

- **Black-box fuzzing has a hole I have not closed.** A co-fuzzer reduces region-evasion (the measured cheating rate drops from 2 in 6 to 1 in 6 on the adversarial bench), but single-point evasion is still open. I declare it. I have not solved it.
- **CONFIRMED is bounded, not universal.** Several of the passing results are exhaustive over a declared input bound, not a proof over all inputs. The certificate says so, and you should hold me to it. I will not call a bounded-exhaustive check a universal proof.
- **There is no source-to-certificate binding today.** The signature covers the kernel's verdict, not a cryptographic link to the exact source that produced it. That is a real gap and it is on the list.
- **It is single-author and not production-hardened.** Bus-factor one. The two audit passes were thorough but "no soundness hole found by two passes" is not "proven sound."
- **The hard, unsolved problem is specification elicitation.** Everything above works because the domain *has* a checkable spec: regex semantics, vault invariants, packet acceptance. The solver needs a formal specification, and most model outputs do not come with one. The open question that gates the entire category is: how far can the cost of obtaining a usable specification be lowered, and where does that boundary actually sit? I do not have a general answer. Whoever finds one opens the category.

## 6. What this is not

It is not a universal judge for arbitrary text. It does not tell you whether a poem is good or a summary is faithful. It wins on the *verifiable slice*: code, mathematics, structured data, formalized rules, smart contracts. Everywhere else it abstains, and abstaining honestly is part of the design. The pitch is not a smarter model. It is a floor under the model you are forced to trust. The prover proposes, deterministic execution disposes.

## 7. Why this is a safety problem

As models get better at producing convincing wrong answers, the bottleneck is not generating candidate answers, it is trusting them. A checker that cannot overclaim, that returns proofs for refutations and honestly bounded evidence for confirmations, is a load-bearing primitive for anyone who has to act on model output in a domain where being wrong is expensive. It reduces unjustified trust without making the model more capable, which is the direction of safety work I care about. The framing is the same one the "guaranteed safe AI" agenda points at: let the untrusted system search, let a small trusted checker decide.

## 8. Reproduce it

The repository contains the kernel, the labelled benchmark, and example certificates. Honest note on the headline command: on a clean checkout with the solver toolchain installed (`pip install -e ".[full]"`), the reproducible suite runs ~123 deterministic checks green plus a couple of honest skips (the real-mainnet eth-getProof leg needs a pinned py-trie; the ERC-4626 exec-gate needs Foundry's `forge` + the `verivault` package). Skips are reported, never silently passed, and there are no failures. I would rather state that than claim a round "all green." A standalone browser verifier rechecks any signed certificate with no install.

If you work on guaranteed-safe AI, proof-carrying code, or evaluation, I would rather you try to break this than take my word for it. Counterexamples to the address below.

---

*Daniel Culotta. github.com/Dan23RR. daniel.culotta@gmail.com. Prior work: "RoPE Is a Substrate, Not a Trick" (Zenodo 10.5281/zenodo.19899195) and "Behavioral Trust Clustering" (Zenodo 10.5281/zenodo.20028123).*
