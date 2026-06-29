# substrate-verify

**A deterministic verification kernel for AI output. The model proposes, execution disposes.**

Most tools check a language model's output by asking a second model whether it looks right. This one checks a claim by **executing** it against a specification, and returns a signed certificate you can rerun yourself. A refutation is an executed counterexample and counts as a proof. A confirmation is execution-backed evidence tagged with the assurance it actually earned, and is not treated as a proof. An abstention is a typed reason for not deciding, never a silent pass.

The one design decision everything rests on: **a refutation is a proof, a confirmation is not.** The kernel enforces this with an assurance lattice so a verdict can never be labelled stronger than the evidence behind it. Overclaim is impossible to express.

## Why

On a labelled set of ERC-4626 smart-contract vaults, ten independent LLM auditors produced both false positives and false negatives (10 of 10 false-positive on a safe vault, 40% miss on a real bug). The deterministic checker classified the same set with neither, and emitted a witness you can rerun. Wherever an output has checkable structure (code, math, structured data, rules, contracts), executing the check beats grading it with a bigger model.

## How it works

```
untrusted prover  ->  falsifiable claim  ->  [ trusted kernel, ~300 lines ]  ->  verdict + signed certificate
                                                                                    REFUTED  (executed counterexample, a proof)
                                                                                    CONFIRMED (execution-backed, tagged tier)
                                                                                    ABSTAIN  (typed reason, never a fake pass)
```

Certificates are Ed25519-signed, content-hashed, rerun offline, and compose weakest-link across domains.

## Results

| Claim | Evidence | Tier |
|---|---|---|
| Regex equivalence, real corpus | 1000 GitHub patterns, 111 signed equivalence collapses, 72 hidden multi-syntax equivalences | proven (SMT) |
| Bounded constitution check | 780/780 admitted, malicious rejected (780 reproduced from first principles) | bounded-exhaustive, not universal |
| Firewall rule-set equivalence | 8/8, refutation is a concrete packet rerun against a first-match interpreter | proven (SMT, QF_BV) |
| ERC-4626 exec-gate | 0 false positives / 0 false negatives on 7 labelled vaults; 22 live vaults: 16 immune, 0 vulnerable, 6 abstain | empirical, executed witness |
| vs LLM-as-judge | judges 10/10 FP + 40% miss; exec-gate 0/0 | measured |

Re-checked by two adversarial audit passes (2026-06-05, 2026-06-06) that re-ran every script and recomputed the certificates by hand. They found only circumscribed cosmetic overclaims (since fixed) and no soundness hole.

## Quickstart

```bash
# clone, then from the repo root:
pip install -e ".[full]"   # core + solver toolchain (Z3, wasmtime); plain `pip install -e .` works too
python verify_all.py
```

Honest note on the headline command: with the solver toolchain installed (`[full]`), `verify_all.py` runs **123 deterministic checks green with 2 honest skips and 0 failures** (`ALL GREEN`, exit 0). The skips are the real-mainnet eth-getProof leg (needs a pinned `py-trie`) and the ERC-4626 exec-gate (needs Foundry's `forge` + the `verivault` package); install those and they go green too. Skips are reported, never silently passed. To run the full acceptance gate (board + every regression oracle): `python audit_regression/run_all.py`.

A standalone browser verifier under `verifier/` re-checks any signed certificate: load it, drop in a `.scar` / certificate JSON, then flip one byte and watch it go red.

## Layout

```
substrate_core/  the trusted kernel, adjudicators, SMT/signing/lattice
verivault/       the ERC-4626 exec-gate vertical (Foundry/forge)
benchmarks/      labelled corpora (regex GitHub set, firewall ACLs)
examples/        example signed certificates (.scar) you can rerun
verifier/        standalone browser certificate verifier (no install)
docs/            ASSURANCE.md (assurance model) + WRITEUP.md
scripts/         prepublish_check.sh (secret / overclaim gate)
verify_all.py    one-command reproducible suite
```

## Limitations (read this)

- Black-box fuzzing: single-point evasion is still open (co-fuzzer drops region-evasion from 2/6 to 1/6, not to 0).
- CONFIRMED is bounded-exhaustive over a declared bound, not a universal proof. The certificate records which.
- No source-to-certificate binding yet: the signature covers the verdict, not a link to the exact source.
- Single-author research prototype, not production-hardened.
- The hard open problem is cheap **specification elicitation** for outputs that do not come with a spec. That is the research frontier, not a solved feature.

Full discussion in the write-up (`docs/WRITEUP.md`).

## What this is not

Not a universal judge for arbitrary text. It wins on the verifiable slice and abstains elsewhere, honestly. The value is a floor under the model you are forced to trust, not a smarter model.

## Citing

See `CITATION.cff`. Prior work: *RoPE Is a Substrate, Not a Trick* (Zenodo 10.5281/zenodo.19899195) and *Behavioral Trust Clustering* (Zenodo 10.5281/zenodo.20028123).

## License

MIT. See `LICENSE`.

## Contact

Daniel Culotta. daniel.culotta@gmail.com. github.com/Dan23RR. Counterexamples welcome.
